"""Pruebas del Bloque 1 v1.0: Reporte Excel (.xlsx), Multi-gasto, Ritmo y Seed Demo."""

import io
from pathlib import Path
import zipfile
import pytest

from scripts.seed_demo import poblar_datos_demo
from src.database import (
    editar_transaccion,
    eliminar_transaccion_usuario,
    guardar_presupuesto,
    listar_transacciones,
)
from src.servicios import (
    MENSAJE_CSV_VACIO,
    calcular_ritmo_gasto,
    dividir_frase_multigasto,
    exportar_reporte_excel,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
)


def test_multigasto_en_una_sola_frase_y_edicion_eliminacion(tmp_path: Path) -> None:
    """Verifica registro múltiple ('almuerzo 15 mil, gasolina 20 lucas y ...')."""
    ruta_db = tmp_path / "test_multigasto.db"
    guardar_presupuesto(1000000, ruta_db, usuario_id=1, periodo="2026-11")

    frase = "almuerzo 15 mil, gasolina moto 20 lucas y fotocopias 3000"
    fragmentos = dividir_frase_multigasto(frase)
    assert len(fragmentos) == 3

    res = registrar_gasto_desde_texto(
        frase,
        sub_etiqueta="Jornada universidad",
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res["registrado"] is True
    assert res["es_multigasto"] is True
    assert res["cantidad_registrados"] == 3
    assert "$38.000" in res["mensaje"]

    lista = listar_transacciones(ruta_db=ruta_db, usuario_id=1, periodo="2026-11")
    assert len(lista) == 3
    categorias = {item["categoria"] for item in lista}
    assert {"Alimentación", "Transporte/Moto", "Estudio"} == categorias

    # Editar el movimiento más reciente y verificar recálculo
    tx_id = int(lista[0]["id"])
    editado = editar_transaccion(
        tx_id,
        concepto="Fotocopias y anillado",
        monto=12000,
        categoria="Estudio",
        sub_etiqueta="Tesis",
        usuario_id=1,
        ruta_db=ruta_db,
    )
    assert editado is True

    resumen_1 = obtener_resumen_financiero(
        ruta_db=ruta_db, usuario_id=1, periodo="2026-11"
    )
    assert resumen_1["total_gastado"] == 47000

    # Eliminar movimiento y comprobar recálculo de saldo
    eliminado = eliminar_transaccion_usuario(tx_id, usuario_id=1, ruta_db=ruta_db)
    assert eliminado is True
    resumen_2 = obtener_resumen_financiero(
        ruta_db=ruta_db, usuario_id=1, periodo="2026-11"
    )
    assert resumen_2["total_gastado"] == 35000


@pytest.mark.parametrize(
    ("pct_consumo", "en_sobregiro", "dia_mes", "estado_esperado"),
    [
        # Consumo (20%) acorde al día 10 de 30 (33.3%) -> Ritmo saludable
        (20.0, False, 10, "Ritmo saludable"),
        # Consumo (45%) ligeramente mayor al día 10 de 30 (33.3%) -> Ritmo moderado
        (45.0, False, 10, "Ritmo moderado"),
        # Consumo (75%) muy superior al día 10 de 30 (33.3%) -> Consumo acelerado
        (75.0, False, 10, "Consumo acelerado"),
        # En sobregiro siempre reporta Consumo acelerado
        (110.0, True, 28, "Consumo acelerado"),
    ],
)
def test_indicador_ritmo_de_gasto_burn_rate(
    pct_consumo: float,
    en_sobregiro: bool,
    dia_mes: int,
    estado_esperado: str,
) -> None:
    """Verifica las particiones del indicador de Ritmo de Gasto (Burn Rate)."""
    ritmo = calcular_ritmo_gasto(
        porcentaje_consumo=pct_consumo,
        presupuesto_configurado=True,
        en_sobregiro=en_sobregiro,
        periodo="2026-11",
        dia_referencia=dia_mes,
    )
    assert ritmo["estado"] == estado_esperado


def test_exportacion_excel_xlsx_tres_hojas_y_seed_demo(tmp_path: Path) -> None:
    """Verifica generación del archivo Excel (.xlsx) con 3 hojas y script seed_demo."""
    ruta_db = tmp_path / "test_excel_demo.db"

    with pytest.raises(ValueError, match=f"^{MENSAJE_CSV_VACIO}$"):
        exportar_reporte_excel(ruta_db=ruta_db, usuario_id=1, periodo="2026-11")

    info_demo = poblar_datos_demo(ruta_db=ruta_db)
    uid = int(info_demo["usuario_id"])

    nombre_xlsx, bytes_xlsx = exportar_reporte_excel(
        ruta_db=ruta_db,
        usuario_id=uid,
        nombre_usuario="Cuenta Demo Bolsillo",
        periodo="2026-11",
    )
    assert nombre_xlsx == "Reporte_Finanzas_2026_11.xlsx"
    assert bytes_xlsx[:2] == b"PK"

    with zipfile.ZipFile(io.BytesIO(bytes_xlsx), mode="r") as archivo_zip:
        nombres_internos = set(archivo_zip.namelist())
        assert "xl/workbook.xml" in nombres_internos
        assert "xl/worksheets/sheet1.xml" in nombres_internos
        assert "xl/worksheets/sheet2.xml" in nombres_internos
        assert "xl/worksheets/sheet3.xml" in nombres_internos
        workbook_xml = archivo_zip.read("xl/workbook.xml").decode("utf-8")
        assert "Resumen Mensual" in workbook_xml
        assert "Movimientos" in workbook_xml
        assert "Compromisos y Créditos" in workbook_xml

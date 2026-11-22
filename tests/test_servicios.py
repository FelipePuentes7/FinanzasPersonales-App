"""Pruebas unitarias y de integración para la lógica de negocio (src/servicios.py)."""

from pathlib import Path
import pytest

from src.database import guardar_presupuesto
from src.servicios import (
    MENSAJE_ALERTA_SOBREGIRO,
    MENSAJE_CSV_VACIO,
    MENSAJE_GASTO_REGISTRADO,
    MENSAJE_MONTO_AMBIGUO,
    MENSAJE_PRESUPUESTO_NO_ESTABLECIDO,
    MENSAJE_SIN_MONTO_VALIDO,
    exportar_transacciones_csv,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
)


def test_registro_gasto_estandar_y_metricas_dashboard(tmp_path: Path) -> None:
    """Verifica HU-01 Esc. 1 y HU-04 Esc. 1: registro, saldo y barra al 36.6%."""
    ruta_db = tmp_path / "test_finanzas.db"
    guardar_presupuesto(600000, ruta_db)

    res_1 = registrar_gasto_desde_texto("almuerzo corriente 14000", ruta_db=ruta_db)
    assert res_1["registrado"] is True
    assert res_1["mensaje"] == MENSAJE_GASTO_REGISTRADO
    assert res_1["transaccion"]["concepto"] == "Almuerzo corriente"
    assert res_1["transaccion"]["monto"] == 14000
    assert res_1["transaccion"]["categoria"] == "Alimentación"

    registrar_gasto_desde_texto("206 lucas de gasolina para la moto", ruta_db=ruta_db)

    resumen = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen["presupuesto_fmt"] == "$600.000"
    assert resumen["total_gastado_fmt"] == "$220.000"
    assert resumen["saldo_disponible_fmt"] == "$380.000 disponible"
    assert resumen["porcentaje_consumo"] == 36.6
    assert resumen["en_sobregiro"] is False


def test_errores_texto_sin_monto_y_monto_ambiguo(tmp_path: Path) -> None:
    """Verifica HU-01 Esc. 2 (sin monto) y HU-02 Esc. 2 (media luca)."""
    ruta_db = tmp_path / "test_finanzas.db"

    with pytest.raises(ValueError, match=f"^{MENSAJE_SIN_MONTO_VALIDO}$"):
        registrar_gasto_desde_texto("tanqueé la moto en la mañana", ruta_db=ruta_db)

    with pytest.raises(ValueError, match=r"^Monto ambiguo\."):
        registrar_gasto_desde_texto("gasté media luca en dulces", ruta_db=ruta_db)

    resumen = obtener_resumen_financiero(ruta_db=ruta_db)
    assert len(resumen["transacciones"]) == 0
    assert MENSAJE_MONTO_AMBIGUO.startswith("Monto ambiguo")


def test_panel_sin_presupuesto_inicializado(tmp_path: Path) -> None:
    """Verifica HU-04 Esc. 2: tarjetas con '?' y mensaje de presupuesto pendiente."""
    ruta_db = tmp_path / "test_finanzas.db"
    resumen = obtener_resumen_financiero(ruta_db=ruta_db)

    assert resumen["presupuesto_configurado"] is False
    assert resumen["presupuesto_fmt"] == "?"
    assert resumen["saldo_disponible_fmt"] == "?"
    assert resumen["mensaje_presupuesto"] == MENSAJE_PRESUPUESTO_NO_ESTABLECIDO


def test_alerta_preventiva_mas_del_50_por_ciento_y_sobregiro(tmp_path: Path) -> None:
    """Verifica HU-06 Esc. 1 y 2: confirmación >50% (62.5%) y sobregiro (-$15.000)."""
    ruta_db = tmp_path / "test_finanzas.db"
    guardar_presupuesto(400000, ruta_db)

    preventivo = registrar_gasto_desde_texto(
        "reparación motora 250000",
        confirmado=False,
        ruta_db=ruta_db,
    )
    assert preventivo["registrado"] is False
    assert preventivo["requiere_confirmacion"] is True
    assert "62.5%" in preventivo["mensaje"]

    confirmado = registrar_gasto_desde_texto(
        "reparación motora 250000",
        confirmado=True,
        ruta_db=ruta_db,
    )
    assert confirmado["registrado"] is True

    registrar_gasto_desde_texto("mercado 70000", ruta_db=ruta_db)

    sobregiro = registrar_gasto_desde_texto("compra chaqueta 95000", ruta_db=ruta_db)
    assert sobregiro["registrado"] is True
    assert sobregiro["alerta_sobregiro"] == MENSAJE_ALERTA_SOBREGIRO

    resumen = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen["en_sobregiro"] is True
    assert resumen["saldo_disponible"] == -15000
    assert resumen["saldo_disponible_fmt"] == "-$15.000"


def test_filtrado_categoria_vacia_y_exportacion_csv(tmp_path: Path) -> None:
    """Verifica HU-07 Esc. 2 y HU-08 Esc. 1 y 2: CSV vacío bloqueado y CSV válido."""
    ruta_db = tmp_path / "test_finanzas.db"

    with pytest.raises(ValueError, match=f"^{MENSAJE_CSV_VACIO}$"):
        exportar_transacciones_csv(ruta_db=ruta_db)

    registrar_gasto_desde_texto("fotocopias taller de sistemas 4500", ruta_db=ruta_db)

    resumen_ocio = obtener_resumen_financiero(
        categoria_filtro="Ocio",
        ruta_db=ruta_db,
    )
    assert (
        resumen_ocio["mensaje_filtro_vacio"]
        == "No se encontraron transacciones registradas para la categoría "
        "'Ocio' en este periodo"
    )

    nombre_csv, contenido_csv = exportar_transacciones_csv(
        ruta_db=ruta_db,
        mes_anio="octubre_2026",
    )
    assert nombre_csv == "gastos_octubre_2026.csv"
    lineas = contenido_csv.strip().split("\n")
    assert lineas[0] == "id,fecha,concepto,monto,categoria"
    assert "Fotocopias taller de sistemas,4500,Estudio" in lineas[1]

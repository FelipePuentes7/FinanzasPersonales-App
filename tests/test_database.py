"""Pruebas unitarias y de abuso para la capa de persistencia SQLite (database.py)."""

from pathlib import Path
import pytest

from src.database import (
    MENSAJE_PRESUPUESTO_INVALIDO,
    actualizar_categoria_transaccion,
    guardar_presupuesto,
    inicializar_db,
    insertar_transaccion,
    listar_transacciones,
    obtener_presupuesto,
)


def test_presupuesto_no_inicializado_retorna_none(tmp_path: Path) -> None:
    """Verifica HU-04 Escenario 2: sin presupuesto previo retorna None."""
    ruta_db = tmp_path / "test_finanzas.db"
    inicializar_db(ruta_db)
    assert obtener_presupuesto(ruta_db) is None


def test_guardar_y_actualizar_presupuesto_mensual(tmp_path: Path) -> None:
    """Verifica HU-05 Escenario 1: guarda 500000 y actualiza el tope a 750000."""
    ruta_db = tmp_path / "test_finanzas.db"
    assert guardar_presupuesto(500000, ruta_db) == 500000
    assert obtener_presupuesto(ruta_db) == 500000

    assert guardar_presupuesto(750000, ruta_db) == 750000
    assert obtener_presupuesto(ruta_db) == 750000


def test_rechazar_presupuesto_negativo_o_cero(tmp_path: Path) -> None:
    """Verifica HU-05 Escenario 2: rechaza presupuesto <= 0 con mensaje exacto."""
    ruta_db = tmp_path / "test_finanzas.db"
    with pytest.raises(ValueError, match=f"^{MENSAJE_PRESUPUESTO_INVALIDO}$"):
        guardar_presupuesto(-50000, ruta_db)

    with pytest.raises(ValueError, match=f"^{MENSAJE_PRESUPUESTO_INVALIDO}$"):
        guardar_presupuesto(0, ruta_db)


def test_insertar_y_filtrar_transacciones_por_categoria(tmp_path: Path) -> None:
    """Verifica HU-01 y HU-07: inserción parametrizada y filtrado offline."""
    ruta_db = tmp_path / "test_finanzas.db"
    id_1 = insertar_transaccion(
        concepto="Almuerzo corriente",
        monto=14000,
        categoria="Alimentación",
        fecha="2026-10-24",
        ruta_db=ruta_db,
    )
    id_2 = insertar_transaccion(
        concepto="Gasolina para la moto",
        monto=20000,
        categoria="Transporte/Moto",
        fecha="2026-10-24",
        ruta_db=ruta_db,
    )

    assert id_1 == 1
    assert id_2 == 2

    todas = listar_transacciones(ruta_db=ruta_db)
    assert len(todas) == 2

    solo_moto = listar_transacciones(categoria="Transporte/Moto", ruta_db=ruta_db)
    assert len(solo_moto) == 1
    assert solo_moto[0]["concepto"] == "Gasolina para la moto"
    assert solo_moto[0]["monto"] == 20000

    sin_ocio = listar_transacciones(categoria="Ocio", ruta_db=ruta_db)
    assert len(sin_ocio) == 0


def test_corregir_categoria_transaccion_ambigua(tmp_path: Path) -> None:
    """Verifica HU-03 Escenario 2: reclasificar gasto ambiguo limpia bandera."""
    ruta_db = tmp_path / "test_finanzas.db"
    tx_id = insertar_transaccion(
        concepto="Pago asunto x",
        monto=30000,
        categoria="Gastos Varios",
        es_ambiguo=True,
        ruta_db=ruta_db,
    )

    inicial = listar_transacciones(ruta_db=ruta_db)[0]
    assert inicial["es_ambiguo"] is True

    actualizado = actualizar_categoria_transaccion(tx_id, "Estudio", ruta_db)
    assert actualizado is True

    corregido = listar_transacciones(ruta_db=ruta_db)[0]
    assert corregido["categoria"] == "Estudio"
    assert corregido["es_ambiguo"] is False


def test_prevencion_inyeccion_sql_en_concepto(tmp_path: Path) -> None:
    """Prueba de abuso de seguridad: un payload SQL en concepto se guarda literal."""
    ruta_db = tmp_path / "test_finanzas.db"
    payload_sql = "almuerzo'; DROP TABLE transacciones; --"
    insertar_transaccion(
        concepto=payload_sql,
        monto=15000,
        categoria="Alimentación",
        ruta_db=ruta_db,
    )

    registros = listar_transacciones(ruta_db=ruta_db)
    assert len(registros) == 1
    assert registros[0]["concepto"] == payload_sql

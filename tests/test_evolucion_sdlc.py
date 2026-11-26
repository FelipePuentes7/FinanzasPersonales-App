"""Pruebas unitarias y de integración para la evolución SDLC (HU-09, HU-10, HU-11)."""

from pathlib import Path
import pytest

from src.database import (
    MENSAJE_CREDITO_SALDADO,
    MENSAJE_GASTO_FIJO_INVALIDO,
    MENSAJE_INGRESO_INVALIDO,
    crear_credito,
    crear_gasto_fijo,
    eliminar_gasto_fijo,
    guardar_presupuesto,
    insertar_ingreso_extra,
    listar_creditos,
    listar_gastos_fijos,
)
from src.servicios import (
    aplicar_gasto_fijo_al_mes,
    es_frase_ingreso_extra,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
    registrar_ingreso_desde_texto,
    registrar_pago_cuota_credito,
)


def test_hu09_recuperacion_saldo_negativo_con_ingreso_extra(tmp_path: Path) -> None:
    """Verifica HU-09 Esc. 1: presupuesto 2M, gasto 3M (-1M), ingreso 1.2M -> +200k."""
    ruta_db = tmp_path / "test_hu09.db"
    guardar_presupuesto(2000000, ruta_db=ruta_db)

    registrar_gasto_desde_texto(
        "reparación general moto 3000000",
        confirmado=True,
        ruta_db=ruta_db,
    )
    resumen_sobregiro = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen_sobregiro["en_sobregiro"] is True
    assert resumen_sobregiro["saldo_disponible"] == -1000000
    assert resumen_sobregiro["saldo_disponible_fmt"] == "-$1.000.000"

    assert es_frase_ingreso_extra("me entraron 1.200.000 de trabajo extra") is True
    res_ingreso = registrar_ingreso_desde_texto(
        "me entraron 1.200.000 de trabajo extra",
        ruta_db=ruta_db,
    )
    assert res_ingreso["registrado"] is True
    assert res_ingreso["ingreso"]["monto"] == 1200000

    resumen_recuperado = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen_recuperado["total_ingresos_extra"] == 1200000
    assert resumen_recuperado["capacidad_total"] == 3200000
    assert resumen_recuperado["saldo_disponible"] == 200000
    assert resumen_recuperado["saldo_disponible_fmt"] == "$200.000 disponible"
    assert resumen_recuperado["en_sobregiro"] is False
    assert resumen_recuperado["alerta_sobregiro"] is None


@pytest.mark.parametrize(
    "monto_invalido",
    [
        # Límite superior inválido: ingreso en cero (0)
        0,
        # Límite negativo inmediato: (-1)
        -1,
        # Partición inválida: booleano True
        True,
    ],
)
def test_hu09_rechaza_ingreso_extra_no_positivo(
    monto_invalido: int,
    tmp_path: Path,
) -> None:
    """Verifica HU-09 Esc. 2: rechaza ingresos extra con monto <= 0 o booleano."""
    ruta_db = tmp_path / "test_hu09_inv.db"
    with pytest.raises(ValueError, match=f"^{MENSAJE_INGRESO_INVALIDO}$"):
        insertar_ingreso_extra("Abono inválido", monto_invalido, ruta_db=ruta_db)


def test_hu10_creacion_aplicacion_y_eliminacion_gastos_fijos(tmp_path: Path) -> None:
    """Verifica HU-10 Esc. 1 y 2: crear gasto fijo, aplicarlo al mes y validar monto."""
    ruta_db = tmp_path / "test_hu10.db"
    guardar_presupuesto(1500000, ruta_db=ruta_db)

    with pytest.raises(ValueError, match=f"^{MENSAJE_GASTO_FIJO_INVALIDO}$"):
        crear_gasto_fijo("Arriendo", 0, "Gastos Varios", ruta_db=ruta_db)

    fijo_id = crear_gasto_fijo(
        "Arriendo habitación",
        650000,
        "Gastos Varios",
        ruta_db=ruta_db,
    )
    lista = listar_gastos_fijos(ruta_db=ruta_db)
    assert len(lista) == 1
    assert lista[0]["nombre"] == "Arriendo habitación"

    aplicado = aplicar_gasto_fijo_al_mes(fijo_id, ruta_db=ruta_db)
    assert aplicado["registrado"] is True
    assert aplicado["transaccion"]["concepto"] == "Gasto fijo: Arriendo habitación"
    assert aplicado["transaccion"]["monto"] == 650000

    resumen = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen["total_gastado"] == 650000
    assert resumen["saldo_disponible"] == 850000

    assert eliminar_gasto_fijo(fijo_id, ruta_db=ruta_db) is True
    assert len(listar_gastos_fijos(ruta_db=ruta_db)) == 0


def test_hu11_control_creditos_pago_cuotas_y_bloqueo_saldado(tmp_path: Path) -> None:
    """Verifica HU-11 Esc. 1 y 2: avance de cuotas, impacto en saldo y límite N/N."""
    ruta_db = tmp_path / "test_hu11.db"
    guardar_presupuesto(1000000, ruta_db=ruta_db)

    cred_id = crear_credito(
        nombre="Crédito Moto Yamaha",
        valor_cuota=320000,
        total_cuotas=12,
        cuotas_pagadas=10,
        categoria="Transporte/Moto",
        ruta_db=ruta_db,
    )

    pago_11 = registrar_pago_cuota_credito(cred_id, ruta_db=ruta_db)
    assert pago_11["registrado"] is True
    assert pago_11["credito"]["cuotas_pagadas"] == 11
    assert pago_11["credito"]["cuotas_restantes"] == 1
    assert pago_11["credito"]["saldo_pendiente"] == 320000
    assert pago_11["transaccion"]["concepto"] == "Cuota 11/12: Crédito Moto Yamaha"

    pago_12 = registrar_pago_cuota_credito(cred_id, ruta_db=ruta_db)
    assert pago_12["credito"]["cuotas_pagadas"] == 12
    assert pago_12["credito"]["cuotas_restantes"] == 0
    assert pago_12["credito"]["pagado_completo"] is True

    # Límite N/N: intentar pagar la cuota 13 de 12 debe lanzar ValueError exacto
    with pytest.raises(ValueError, match=f"^{MENSAJE_CREDITO_SALDADO}$"):
        registrar_pago_cuota_credito(cred_id, ruta_db=ruta_db)

    creditos = listar_creditos(ruta_db=ruta_db)
    assert creditos[0]["cuotas_pagadas"] == 12
    resumen = obtener_resumen_financiero(ruta_db=ruta_db)
    assert resumen["total_gastado"] == 640000
    assert resumen["saldo_disponible"] == 360000

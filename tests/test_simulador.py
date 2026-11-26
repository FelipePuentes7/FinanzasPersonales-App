"""Pruebas unitarias y de integración para el Simulador de Viabilidad de Compra."""

import json
from pathlib import Path
import pytest

from app import ClientePruebaWeb, crear_app
from src.database import crear_gasto_fijo, guardar_presupuesto, listar_creditos
from src.simulador import (
    MENSAJE_CONCEPTO_SIMULACION_VACIO,
    MENSAJE_CUOTAS_INVALIDAS,
    MENSAJE_PRESUPUESTO_REQUERIDO_SIMULADOR,
    registrar_compra_simulada,
    simular_viabilidad_compra,
)


def test_simulador_compra_contado_viable_verde(tmp_path: Path) -> None:
    """Verifica diagnóstico VERDE (VIABLE) cuando hay liquidez y baja compromisión."""
    ruta_db = tmp_path / "test_sim_verde.db"
    guardar_presupuesto(2000000, ruta_db, usuario_id=1, periodo="2026-11")
    crear_gasto_fijo(
        "Internet hogar",
        100000,
        "Estudio",
        usuario_id=1,
        ruta_db=ruta_db,
    )

    res = simular_viabilidad_compra(
        "Chaqueta impermeable moto",
        "200 lucas",
        cuotas=1,
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res["ok"] is True
    assert res["monto_total"] == 200000
    assert res["nuevo_saldo_disponible"] == 1800000
    assert res["color_semaforo"] == "VERDE"
    assert res["diagnostico"] == "VIABLE"
    assert res["porcentaje_compromision"] == pytest.approx(15.0, abs=0.1)


def test_simulador_compra_contado_roja_y_alternativa_a_cuotas(tmp_path: Path) -> None:
    """Verifica diagnóstico ROJO por sobregiro de contado y sugerencia a cuotas."""
    ruta_db = tmp_path / "test_sim_rojo.db"
    guardar_presupuesto(1500000, ruta_db, usuario_id=1, periodo="2026-11")

    res_contado = simular_viabilidad_compra(
        "Portátil para universidad",
        "1.800.000",
        cuotas=1,
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res_contado["color_semaforo"] == "ROJO"
    assert res_contado["diagnostico"] == "NO RECOMENDADO / RIESGO DE SOBREGIRO"
    assert res_contado["nuevo_saldo_disponible"] == -300000
    assert res_contado["cuotas_sugeridas"] in (3, 6, 12)
    assert "Alternativa sugerida" in res_contado["mensaje_sugerencia"]

    # Al diferir ese mismo portátil a 6 cuotas ($300.000/mes), pasa a VERDE (20% < 50%)
    res_cuotas = simular_viabilidad_compra(
        "Portátil para universidad",
        1800000,
        cuotas=6,
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res_cuotas["valor_cuota"] == 300000
    assert res_cuotas["nuevo_saldo_disponible"] == 1200000
    assert res_cuotas["color_semaforo"] == "VERDE"


def test_simulador_diagnostico_amarillo_con_precaucion(tmp_path: Path) -> None:
    """Verifica diagnóstico AMARILLO cuando la compromisión queda entre 50% y 75%."""
    ruta_db = tmp_path / "test_sim_amarillo.db"
    guardar_presupuesto(1000000, ruta_db, usuario_id=1, periodo="2026-11")
    crear_gasto_fijo("Arriendo", 450000, "Gastos Varios", usuario_id=1, ruta_db=ruta_db)

    # Cuota de 150.000 + 450.000 fijos = 600.000 (60% de 1.000.000 -> AMARILLO)
    res = simular_viabilidad_compra(
        "Llantas nuevas moto",
        "450 lucas",
        cuotas=3,
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res["valor_cuota"] == 150000
    assert res["porcentaje_compromision"] == pytest.approx(60.0, abs=0.1)
    assert res["color_semaforo"] == "AMARILLO"
    assert res["diagnostico"] == "CON PRECAUCIÓN"


@pytest.mark.parametrize(
    ("concepto", "valor", "cuotas", "mensaje_error"),
    [
        # Concepto vacío
        ("   ", "100000", 1, MENSAJE_CONCEPTO_SIMULACION_VACIO),
        # Cuotas menores a 1 (0)
        ("Casco", "200000", 0, MENSAJE_CUOTAS_INVALIDAS),
        # Cuotas mayores a 36 (48)
        ("Casco", "200000", 48, MENSAJE_CUOTAS_INVALIDAS),
        # Monto ambiguo sin cifras ('media luca')
        ("Dulces", "media luca", 1, "Monto ambiguo"),
        # Monto negativo
        ("Casco", -50000, 1, "Monto ambiguo"),
    ],
)
def test_simulador_validaciones_de_error(
    concepto: str,
    valor: str | int,
    cuotas: int,
    mensaje_error: str,
    tmp_path: Path,
) -> None:
    """Verifica rechazo de entradas inválidas en el simulador de compra."""
    ruta_db = tmp_path / "test_sim_err.db"
    guardar_presupuesto(1000000, ruta_db, usuario_id=1, periodo="2026-11")

    with pytest.raises(ValueError, match=mensaje_error):
        simular_viabilidad_compra(
            concepto,
            valor,
            cuotas=cuotas,
            usuario_id=1,
            periodo="2026-11",
            ruta_db=ruta_db,
        )


def test_simulador_sin_presupuesto_y_endpoints_web_confirmacion(
    tmp_path: Path,
) -> None:
    """Verifica error sin presupuesto, endpoint JSON `/api/simular` y confirmación."""
    ruta_db = tmp_path / "test_sim_web.db"
    patron = f"^{MENSAJE_PRESUPUESTO_REQUERIDO_SIMULADOR}$"
    with pytest.raises(ValueError, match=patron):
        simular_viabilidad_compra("Viaje", "500 lucas", ruta_db=ruta_db)

    cliente = ClientePruebaWeb(crear_app(ruta_db))
    resp_sin_sesion = cliente.post(
        "/api/simular",
        {"concepto": "Viaje", "valor": "500 lucas", "cuotas": "1"},
    )
    assert resp_sin_sesion.status_code == 401

    cliente.post(
        "/register",
        {
            "nombre": "Usuario Simulador",
            "email": "simulador@bolsillo.co",
            "password": "ClaveSimulador2026",
        },
    )
    cliente.post("/presupuesto", {"monto_mensual": "2000000", "periodo": "2026-11"})

    resp_api = cliente.post(
        "/api/simular",
        {
            "concepto": "Kit de arrastre moto",
            "valor": "300 lucas",
            "cuotas": "3",
            "periodo": "2026-11",
        },
    )
    assert resp_api.status_code == 200
    datos_json = json.loads(resp_api.text)
    assert datos_json["ok"] is True
    assert datos_json["valor_cuota"] == 100000
    assert datos_json["color_semaforo"] == "VERDE"

    # Confirmar en 1 clic como crédito a 3 cuotas
    resp_conf = cliente.post(
        "/simulador/confirmar",
        {
            "concepto": "Kit de arrastre moto",
            "valor": "300000",
            "cuotas": "3",
            "categoria": "Transporte/Moto",
            "periodo": "2026-11",
        },
    )
    assert resp_conf.status_code == 200
    msg_credito = "Crédito &#x27;Kit de arrastre moto&#x27; creado a 3 cuotas"
    assert msg_credito in resp_conf.text

    creditos = listar_creditos(ruta_db=ruta_db, usuario_id=1)
    assert len(creditos) == 1
    assert creditos[0]["cuotas_pagadas"] == 1
    assert creditos[0]["total_cuotas"] == 3

    # Confirmar compra de contado directamente desde función de servicio
    res_contado = registrar_compra_simulada(
        "Guantes moto",
        "80 lucas",
        cuotas=1,
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    assert res_contado["registrado"] is True
    assert res_contado["modalidad"] == "contado"

"""Pruebas de autenticación scrypt, aislamiento multiusuario y rollover mensual."""

from pathlib import Path
import pytest

from src.auth import (
    MENSAJE_CREDENCIALES_INVALIDAS,
    MENSAJE_EMAIL_DUPLICADO,
    autenticar_usuario,
    check_password_hash,
    generate_password_hash,
    registrar_usuario,
)
from src.database import (
    actualizar_categoria_transaccion,
    crear_credito,
    crear_gasto_fijo,
    guardar_meta_ahorro,
    guardar_presupuesto,
    listar_transacciones,
)
from src.servicios import (
    aplicar_gasto_fijo_al_mes,
    cerrar_y_avanzar_mes,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
    registrar_ingreso_desde_texto,
    registrar_pago_cuota_credito,
)


def test_hu12_hash_scrypt_registro_y_login_seguro(tmp_path: Path) -> None:
    """Verifica que las contraseñas usen scrypt con sal y validen credenciales."""
    ruta_db = tmp_path / "test_auth.db"
    hash_1 = generate_password_hash("ClaveSegura2026!")
    hash_2 = generate_password_hash("ClaveSegura2026!")

    assert hash_1.startswith("scrypt$16384$8$1$")
    assert hash_1 != hash_2
    assert check_password_hash(hash_1, "ClaveSegura2026!") is True
    assert check_password_hash(hash_1, "ClaveIncorrecta") is False

    usuario = registrar_usuario(
        "Camila Gómez",
        "camila@ejemplo.co",
        "ClaveSegura2026!",
        ruta_db=ruta_db,
    )
    assert usuario["id"] == 1
    assert usuario["email"] == "camila@ejemplo.co"

    with pytest.raises(ValueError, match=f"^{MENSAJE_EMAIL_DUPLICADO}$"):
        registrar_usuario(
            "Otra Camila",
            "CAMILA@ejemplo.co",
            "OtraClave123",
            ruta_db=ruta_db,
        )

    autenticado = autenticar_usuario(
        "camila@ejemplo.co",
        "ClaveSegura2026!",
        ruta_db=ruta_db,
    )
    assert autenticado["id"] == 1

    with pytest.raises(ValueError, match=f"^{MENSAJE_CREDENCIALES_INVALIDAS}$"):
        autenticar_usuario("camila@ejemplo.co", "MalPassword", ruta_db=ruta_db)


def test_hu12_aislamiento_estricto_entre_usuario_a_y_usuario_b(
    tmp_path: Path,
) -> None:
    """Prueba de abuso de control de acceso: Usuario B no ve ni altera datos de A."""
    ruta_db = tmp_path / "test_aislamiento.db"
    user_a = registrar_usuario("Usuario A", "a@test.co", "secretoA1", ruta_db=ruta_db)
    user_b = registrar_usuario("Usuario B", "b@test.co", "secretoB1", ruta_db=ruta_db)
    id_a = user_a["id"]
    id_b = user_b["id"]

    guardar_presupuesto(2000000, ruta_db, usuario_id=id_a, periodo="2026-11")
    guardar_presupuesto(900000, ruta_db, usuario_id=id_b, periodo="2026-11")

    res_tx_a = registrar_gasto_desde_texto(
        "almuerzo ejecutivo 25000",
        usuario_id=id_a,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    tx_id_a = res_tx_a["transaccion"]["id"]

    fijo_id_a = crear_gasto_fijo(
        "Arriendo A",
        700000,
        "Gastos Varios",
        usuario_id=id_a,
        ruta_db=ruta_db,
    )
    cred_id_a = crear_credito(
        "Moto A",
        300000,
        12,
        usuario_id=id_a,
        ruta_db=ruta_db,
    )

    # Usuario B no ve las transacciones de A
    tx_de_b = listar_transacciones(ruta_db=ruta_db, usuario_id=id_b, periodo="2026-11")
    assert len(tx_de_b) == 0

    # Usuario B intenta modificar la categoría de la transacción de A -> False
    alterado = actualizar_categoria_transaccion(
        tx_id_a,
        "Ocio",
        ruta_db=ruta_db,
        usuario_id=id_b,
    )
    assert alterado is False

    # Usuario B intenta aplicar gasto fijo o pagar cuota de crédito de A -> ValueError
    with pytest.raises(ValueError, match="no existe"):
        aplicar_gasto_fijo_al_mes(fijo_id_a, usuario_id=id_b, ruta_db=ruta_db)

    with pytest.raises(ValueError, match="no existe"):
        registrar_pago_cuota_credito(cred_id_a, usuario_id=id_b, ruta_db=ruta_db)


@pytest.mark.parametrize(
    (
        "gasto_octubre",
        "ingreso_octubre",
        "arrastre_esperado",
        "tipo_esperado",
        "saldo_nov_esperado",
    ),
    [
        # Caso ganancia/ahorro: P=1M, G=750k -> +250k se suma a Noviembre (1.25M)
        ("mercado 750000", None, 250000, "ganancia", 1250000),
        # Caso deuda/sobregiro: P=1M, G=1.18M -> -180k se descuenta en Nov (820k)
        ("reparación moto 1180000", None, -180000, "deuda", 820000),
        # Caso equilibrio exacto: P=1M, G=1.2M, I=200k -> 0 arrastrado (1M)
        ("arriendo 1200000", "ingreso 200000", 0, "equilibrio", 1000000),
    ],
)
def test_hu13_rollover_mensual_arrastre_ganancia_deuda_y_equilibrio(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    gasto_octubre: str,
    ingreso_octubre: str | None,
    arrastre_esperado: int,
    tipo_esperado: str,
    saldo_nov_esperado: int,
    tmp_path: Path,
) -> None:
    """Verifica que el cierre mensual arrastre ganancias (+) o deudas (-)."""
    ruta_db = tmp_path / "test_rollover.db"
    guardar_presupuesto(1000000, ruta_db, usuario_id=1, periodo="2026-10")

    registrar_gasto_desde_texto(
        gasto_octubre,
        confirmado=True,
        usuario_id=1,
        periodo="2026-10",
        ruta_db=ruta_db,
    )
    if ingreso_octubre:
        registrar_ingreso_desde_texto(
            ingreso_octubre,
            usuario_id=1,
            periodo="2026-10",
            ruta_db=ruta_db,
        )

    cierre = cerrar_y_avanzar_mes(
        usuario_id=1,
        periodo_actual="2026-10",
        ruta_db=ruta_db,
    )
    assert cierre["periodo_cerrado"] == "2026-10"
    assert cierre["nuevo_periodo"] == "2026-11"
    assert cierre["saldo_arrastrado"] == arrastre_esperado
    assert cierre["tipo_arrastre"] == tipo_esperado

    resumen_nov = obtener_resumen_financiero(
        ruta_db=ruta_db,
        usuario_id=1,
        periodo="2026-11",
    )
    assert resumen_nov["saldo_arrastrado"] == arrastre_esperado
    assert resumen_nov["saldo_disponible"] == saldo_nov_esperado


def test_hu13_meta_ahorro_buscador_y_presupuesto_diario(tmp_path: Path) -> None:
    """Verifica meta de ahorro mensual, presupuesto diario sugerido y buscador."""
    ruta_db = tmp_path / "test_meta.db"
    guardar_presupuesto(1200000, ruta_db, usuario_id=1, periodo="2026-11")
    guardar_meta_ahorro(200000, usuario_id=1, periodo="2026-11", ruta_db=ruta_db)

    registrar_gasto_desde_texto(
        "almuerzo ejecutivo 40000",
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    registrar_gasto_desde_texto(
        "gasolina moto 30000",
        usuario_id=1,
        periodo="2026-11",
        ruta_db=ruta_db,
    )

    resumen = obtener_resumen_financiero(
        ruta_db=ruta_db,
        usuario_id=1,
        periodo="2026-11",
        busqueda="gasolina",
    )
    # Disponible = 1.200.000 - 200.000 (meta ahorro) - 70.000 (gastos) = 930.000
    assert resumen["meta_ahorro"] == 200000
    assert resumen["saldo_disponible"] == 930000
    assert resumen["presupuesto_diario_sugerido"] > 0
    assert len(resumen["transacciones"]) == 1
    assert resumen["transacciones"][0]["concepto"] == "Gasolina moto"

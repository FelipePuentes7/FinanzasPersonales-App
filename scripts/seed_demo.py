"""Script de inicialización de datos sintéticos de demostración para Bolsillo v1.0.

Crea una cuenta de demostración 100% ficticia (sin datos de personas reales) con
contexto colombiano local, historial de 2 meses ('2026-10' cerrado con arrastre
a '2026-11'), ingresos extra, gastos fijos mensuales y créditos a cuotas para
facilitar las pruebas en vivo y la sustentación del proyecto.
"""

from pathlib import Path
import sys
from typing import Any

RUTA_RAIZ = Path(__file__).resolve().parent.parent
if str(RUTA_RAIZ) not in sys.path:
    sys.path.insert(0, str(RUTA_RAIZ))

from src.auth import autenticar_usuario, registrar_usuario  # noqa: E402
from src.database import (  # noqa: E402
    RUTA_DB_DEFECTO,
    crear_credito,
    crear_gasto_fijo,
    guardar_meta_ahorro,
    guardar_presupuesto,
)
from src.servicios import (  # noqa: E402
    cerrar_y_avanzar_mes,
    registrar_gasto_desde_texto,
    registrar_ingreso_desde_texto,
    registrar_pago_cuota_credito,
)

EMAIL_DEMO: str = "demo@bolsillo.co"
CLAVE_DEMO: str = "DemoBolsillo2026"
NOMBRE_DEMO: str = "Cuenta Demo Bolsillo"


def poblar_datos_demo(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Puebla la base de datos SQLite con el usuario y movimientos sintéticos demo.

    Args:
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Resumen con `usuario_id`, `email` y cantidad de registros.
    """
    try:
        usuario = registrar_usuario(
            NOMBRE_DEMO,
            EMAIL_DEMO,
            CLAVE_DEMO,
            ruta_db=ruta_db,
        )
    except ValueError:
        usuario = autenticar_usuario(EMAIL_DEMO, CLAVE_DEMO, ruta_db=ruta_db)

    uid = int(usuario["id"])

    # 1. Mes anterior (Octubre 2026): Presupuesto 1.8M, cierre con +$280.000 a favor
    guardar_presupuesto(1800000, ruta_db=ruta_db, usuario_id=uid, periodo="2026-10")
    registrar_gasto_desde_texto(
        "almuerzo ejecutivo 25 mil, gasolina moto 35 lucas y fotocopias 10000",
        usuario_id=uid,
        periodo="2026-10",
        ruta_db=ruta_db,
    )
    registrar_gasto_desde_texto(
        "mercado mensual supermercado 450000",
        usuario_id=uid,
        periodo="2026-10",
        ruta_db=ruta_db,
    )
    registrar_gasto_desde_texto(
        "pago arriendo 1000000",
        confirmado=True,
        usuario_id=uid,
        periodo="2026-10",
        ruta_db=ruta_db,
    )
    cerrar_y_avanzar_mes(
        usuario_id=uid,
        periodo_actual="2026-10",
        nuevo_presupuesto_base=2000000,
        ruta_db=ruta_db,
    )

    # 2. Mes actual (Noviembre 2026): Meta ahorro, ingreso extra, fijos y créditos
    guardar_meta_ahorro(200000, usuario_id=uid, periodo="2026-11", ruta_db=ruta_db)
    registrar_ingreso_desde_texto(
        "me entraron 350.000 de monitoría académica",
        usuario_id=uid,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    registrar_gasto_desde_texto(
        "almuerzo corriente 16 mil, café en cafetería 6.500 y parqueadero moto 4000",
        sub_etiqueta="Rutina diaria",
        usuario_id=uid,
        periodo="2026-11",
        ruta_db=ruta_db,
    )
    registrar_gasto_desde_texto(
        "cambio aceite y revisión freno moto 85 lucas",
        sub_etiqueta="Mantenimiento",
        usuario_id=uid,
        periodo="2026-11",
        ruta_db=ruta_db,
    )

    crear_gasto_fijo(
        "Arriendo estudio",
        750000,
        "Gastos Varios",
        usuario_id=uid,
        ruta_db=ruta_db,
    )
    crear_gasto_fijo(
        "Internet fibra óptica",
        85000,
        "Estudio",
        usuario_id=uid,
        ruta_db=ruta_db,
    )
    cred_id = crear_credito(
        "Moto Urbana 150cc",
        320000,
        12,
        cuotas_pagadas=4,
        categoria="Transporte/Moto",
        usuario_id=uid,
        ruta_db=ruta_db,
    )
    registrar_pago_cuota_credito(
        cred_id,
        usuario_id=uid,
        periodo="2026-11",
        ruta_db=ruta_db,
    )

    return {
        "usuario_id": uid,
        "email": EMAIL_DEMO,
        "password": CLAVE_DEMO,
        "periodos_creados": ["2026-10", "2026-11"],
    }


if __name__ == "__main__":
    info = poblar_datos_demo()
    print(
        f"Datos demo listos -> Usuario: {info['email']} | Clave: {info['password']}"
    )

"""Motor del Simulador de Viabilidad de Compra ('¿Puedo comprarlo?') para Bolsillo v1.0.

Evalúa el impacto financiero de una compra potencial (de contado o diferida de
2 a 36 cuotas) sobre el saldo disponible y el nivel de endeudamiento mensual
del usuario sin modificar la base de datos SQLite hasta que el usuario decida
confirmar el registro.
"""

import math
from pathlib import Path
from typing import Any

from src.clasificador import clasificar_gasto
from src.database import (
    CATEGORIAS_VALIDAS,
    RUTA_DB_DEFECTO,
    crear_credito,
)
from src.parser_montos import extraer_monto
from src.servicios import (
    formatear_pesos,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
    registrar_pago_cuota_credito,
)

MIN_CUOTAS: int = 1
MAX_CUOTAS: int = 36
UMBRAL_COMPROMISION_VERDE: float = 50.0
UMBRAL_COMPROMISION_AMARILLO: float = 75.0
UMBRAL_MARGEN_SALDO_SEGURO: float = 0.15

MENSAJE_CONCEPTO_SIMULACION_VACIO: str = (
    "El concepto o producto a simular no puede estar vacío"
)
MENSAJE_CUOTAS_INVALIDAS: str = (
    "El número de cuotas debe ser un entero entre 1 y 36"
)
MENSAJE_PRESUPUESTO_REQUERIDO_SIMULADOR: str = (
    "Configure primero su presupuesto mensual para simular una compra"
)


def _normalizar_monto_simulacion(valor_entrada: str | int) -> int:
    """Convierte el valor ingresado (entero o jerga como '800 lucas') a entero COP.

    Args:
        valor_entrada (str | int): Monto numérico o expresión en lenguaje natural.

    Returns:
        int: Valor monetario entero positivo en pesos colombianos.

    Raises:
        ValueError: Si el monto no es válido, es ambiguo o es menor o igual a cero.
    """
    if not isinstance(valor_entrada, bool) and isinstance(valor_entrada, int):
        if valor_entrada <= 0:
            raise ValueError(
                "Monto ambiguo. Por favor indique el valor en cifras numéricas"
            )
        return valor_entrada

    if not isinstance(valor_entrada, str) or not valor_entrada.strip():
        raise ValueError(
            "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        )

    return extraer_monto(valor_entrada.strip())


def _calcular_alternativa_sugerida(
    *,
    monto_total: int,
    cuotas_actuales: int,
    saldo_actual: int,
    capacidad_mensual: int,
    compromisos_actuales: int,
    color_semaforo: str,
    nuevo_saldo: int,
) -> dict[str, Any]:
    """Calcula una recomendación automática de cuotas o ahorro mensual.

    Args:
        monto_total (int): Valor total del producto.
        cuotas_actuales (int): Número de cuotas evaluadas originalmente.
        saldo_actual (int): Saldo disponible antes de la compra.
        capacidad_mensual (int): Capacidad total del mes (`Presupuesto + Ingresos`).
        compromisos_actuales (int): Suma de gastos fijos y cuotas activas actuales.
        color_semaforo (str): Diagnóstico actual (`'VERDE'`, `'AMARILLO'`, `'ROJO'`).
        nuevo_saldo (int): Saldo restante tras aplicar la cuota o pago de contado.

    Returns:
        dict[str, Any]: Diccionario con `cuotas_sugeridas`, `cuota_sugerida_fmt`,
            `ahorro_mensual_sugerido_fmt` y `mensaje_sugerencia`.
    """
    if color_semaforo == "VERDE":
        return {
            "cuotas_sugeridas": cuotas_actuales,
            "cuota_sugerida": math.ceil(monto_total / cuotas_actuales),
            "cuota_sugerida_fmt": formatear_pesos(
                math.ceil(monto_total / cuotas_actuales)
            ),
            "ahorro_mensual_sugerido": 0,
            "ahorro_mensual_sugerido_fmt": "$0",
            "mensaje_sugerencia": (
                f"Compra saludable: conservas {formatear_pesos(nuevo_saldo)} "
                "libres este mes y tus compromisos se mantienen bajo el 50%."
            ),
        }

    opciones_plazo = (3, 6, 12, 18, 24, 36)
    ahorro_3_meses = math.ceil(monto_total / 3)
    ahorro_4_meses = math.ceil(monto_total / 4)

    for plazo in opciones_plazo:
        if plazo <= cuotas_actuales:
            continue
        cuota_plazo = math.ceil(monto_total / plazo)
        saldo_con_plazo = saldo_actual - cuota_plazo
        compromiso_con_plazo = (
            (compromisos_actuales + cuota_plazo) / max(capacidad_mensual, 1)
        ) * 100.0

        if (
            saldo_con_plazo >= (capacidad_mensual * UMBRAL_MARGEN_SALDO_SEGURO)
            and compromiso_con_plazo <= UMBRAL_COMPROMISION_VERDE
        ):
            return {
                "cuotas_sugeridas": plazo,
                "cuota_sugerida": cuota_plazo,
                "cuota_sugerida_fmt": formatear_pesos(cuota_plazo),
                "ahorro_mensual_sugerido": ahorro_3_meses,
                "ahorro_mensual_sugerido_fmt": formatear_pesos(ahorro_3_meses),
                "mensaje_sugerencia": (
                    f"Alternativa sugerida: si lo difieres a {plazo} cuotas de "
                    f"{formatear_pesos(cuota_plazo)}/mes, tu saldo este mes "
                    f"quedaría en {formatear_pesos(saldo_con_plazo)} (Viable). "
                    f"O ahorra {formatear_pesos(ahorro_3_meses)}/mes por 3 meses "
                    "para comprarlo de contado."
                ),
            }

    for plazo in opciones_plazo:
        if plazo <= cuotas_actuales:
            continue
        cuota_plazo = math.ceil(monto_total / plazo)
        saldo_con_plazo = saldo_actual - cuota_plazo
        compromiso_con_plazo = (
            (compromisos_actuales + cuota_plazo) / max(capacidad_mensual, 1)
        ) * 100.0
        if (
            saldo_con_plazo >= 0
            and compromiso_con_plazo <= UMBRAL_COMPROMISION_AMARILLO
        ):
            return {
                "cuotas_sugeridas": plazo,
                "cuota_sugerida": cuota_plazo,
                "cuota_sugerida_fmt": formatear_pesos(cuota_plazo),
                "ahorro_mensual_sugerido": ahorro_4_meses,
                "ahorro_mensual_sugerido_fmt": formatear_pesos(ahorro_4_meses),
                "mensaje_sugerencia": (
                    f"Alternativa para evitar sobregiro: diferirlo a {plazo} cuotas "
                    f"de {formatear_pesos(cuota_plazo)}/mes mantiene tu saldo en "
                    f"{formatear_pesos(saldo_con_plazo)} (Con precaución). "
                    f"Idealmente ahorra {formatear_pesos(ahorro_4_meses)}/mes "
                    "durante 4 meses."
                ),
            }

    return {
        "cuotas_sugeridas": None,
        "cuota_sugerida": 0,
        "cuota_sugerida_fmt": "$0",
        "ahorro_mensual_sugerido": ahorro_4_meses,
        "ahorro_mensual_sugerido_fmt": formatear_pesos(ahorro_4_meses),
        "mensaje_sugerencia": (
            "Plan de ahorro recomendado: actualmente esta compra excede tu margen "
            f"seguro incluso a plazos. Ahorra {formatear_pesos(ahorro_4_meses)}/mes "
            "durante 4 meses para adquirirlo sin endeudarte."
        ),
    }


def simular_viabilidad_compra(  # pylint: disable=too-many-arguments,too-many-locals
    concepto: str,
    valor_entrada: str | int,
    *,
    cuotas: int = 1,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Simula la viabilidad financiera de una compra sin modificar SQLite.

    Evalúa tres niveles de diagnóstico (Semáforo):
    - `VERDE` (`VIABLE`): Nuevo saldo del mes `>= 15%` de la capacidad mensual y
      compromisión mensual total `<= 50%`.
    - `AMARILLO` (`CON PRECAUCIÓN`): Nuevo saldo `>= 0`, pero deja un margen
      menor al `15%` de la capacidad o compromete entre `50%` y `75%`.
    - `ROJO` (`NO RECOMENDADO / RIESGO DE SOBREGIRO`): Deja el saldo del mes en
      negativo (`< 0`) o compromete más del `75%` de la capacidad mensual.

    Args:
        concepto (str): Nombre del producto o servicio que se desea comprar.
        valor_entrada (str | int): Valor total en pesos o jerga ('800 lucas').
        cuotas (int): Cantidad de cuotas (`1` para contado, `2..36` para crédito).
        usuario_id (int): Identificador del usuario autenticado.
        periodo (str | None): Periodo `'YYYY-MM'` evaluado.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Resultado completo de la simulación con semáforo,
            métricas antes/después y alternativa inteligente sugerida.

    Raises:
        ValueError: Si el concepto está vacío, las cuotas están fuera de `1..36`,
            el monto es inválido o el usuario no ha configurado su presupuesto.
    """
    if not isinstance(concepto, str) or not concepto.strip():
        raise ValueError(MENSAJE_CONCEPTO_SIMULACION_VACIO)

    if (
        isinstance(cuotas, bool)
        or not isinstance(cuotas, int)
        or cuotas < MIN_CUOTAS
        or cuotas > MAX_CUOTAS
    ):
        raise ValueError(MENSAJE_CUOTAS_INVALIDAS)

    monto_total = _normalizar_monto_simulacion(valor_entrada)
    resumen = obtener_resumen_financiero(
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    if not resumen["presupuesto_configurado"]:
        raise ValueError(MENSAJE_PRESUPUESTO_REQUERIDO_SIMULADOR)

    capacidad_mensual = max(int(resumen["capacidad_total"] or 0), 1)
    saldo_actual = int(resumen["saldo_disponible"] or 0)
    compromisos_actuales = int(resumen["total_gastos_fijos"]) + int(
        resumen["total_cuotas_activas"]
    )

    valor_cuota = math.ceil(monto_total / cuotas)
    nuevo_saldo = saldo_actual - valor_cuota
    compromisos_proyectados = compromisos_actuales + valor_cuota
    pct_compromision = (
        int((compromisos_proyectados / capacidad_mensual) * 1000) / 10.0
    )
    margen_minimo_seguro = capacidad_mensual * UMBRAL_MARGEN_SALDO_SEGURO

    if nuevo_saldo < 0 or pct_compromision > UMBRAL_COMPROMISION_AMARILLO:
        color = "ROJO"
        etiqueta = "NO RECOMENDADO / RIESGO DE SOBREGIRO"
        clase_css = "semaforo-rojo"
        if nuevo_saldo < 0:
            explicacion = (
                f"Esta compra supera tu saldo disponible actual y te dejaría "
                f"en sobregiro ({formatear_pesos(nuevo_saldo)}) este mes."
            )
        else:
            explicacion = (
                f"Comprometería el {pct_compromision:.1f}% de tu capacidad mensual "
                "(superando el límite máximo recomendado del 75%)."
            )
    elif (
        pct_compromision > UMBRAL_COMPROMISION_VERDE
        or nuevo_saldo < margen_minimo_seguro
    ):
        color = "AMARILLO"
        etiqueta = "CON PRECAUCIÓN"
        clase_css = "semaforo-amarillo"
        explicacion = (
            f"Te alcanza para cubrirlo, pero tu saldo libre bajaría a "
            f"{formatear_pesos(nuevo_saldo)} y comprometerías el "
            f"{pct_compromision:.1f}% de tu capacidad mensual."
        )
    else:
        color = "VERDE"
        etiqueta = "VIABLE"
        clase_css = "semaforo-verde"
        explicacion = (
            f"Puedes realizar la compra con tranquilidad: conservarás "
            f"{formatear_pesos(nuevo_saldo)} disponibles y una carga mensual "
            f"saludable del {pct_compromision:.1f}%."
        )

    alternativa = _calcular_alternativa_sugerida(
        monto_total=monto_total,
        cuotas_actuales=cuotas,
        saldo_actual=saldo_actual,
        capacidad_mensual=capacidad_mensual,
        compromisos_actuales=compromisos_actuales,
        color_semaforo=color,
        nuevo_saldo=nuevo_saldo,
    )
    categoria_inferida, _ = clasificar_gasto(concepto.strip())

    return {
        "ok": True,
        "concepto": concepto.strip(),
        "categoria_sugerida": categoria_inferida,
        "monto_total": monto_total,
        "monto_total_fmt": formatear_pesos(monto_total),
        "modalidad": "contado" if cuotas == 1 else "cuotas",
        "cuotas": cuotas,
        "valor_cuota": valor_cuota,
        "valor_cuota_fmt": formatear_pesos(valor_cuota),
        "saldo_actual": saldo_actual,
        "saldo_actual_fmt": formatear_pesos(saldo_actual),
        "nuevo_saldo_disponible": nuevo_saldo,
        "nuevo_saldo_fmt": formatear_pesos(nuevo_saldo),
        "compromisos_actuales": compromisos_actuales,
        "compromisos_proyectados": compromisos_proyectados,
        "porcentaje_compromision": pct_compromision,
        "porcentaje_barra_impacto": min(max(pct_compromision, 0.0), 100.0),
        "color_semaforo": color,
        "diagnostico": etiqueta,
        "clase_semaforo": clase_css,
        "explicacion": explicacion,
        **alternativa,
    }


def registrar_compra_simulada(  # pylint: disable=too-many-arguments
    concepto: str,
    valor_entrada: str | int,
    *,
    cuotas: int = 1,
    categoria: str | None = None,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Convierte en 1 clic una simulación en gasto de contado o crédito a cuotas.

    - Si `cuotas == 1`, registra el gasto de contado en el periodo activo.
    - Si `cuotas > 1`, crea el crédito en `creditos` y registra el pago de la
      primera cuota (`1/N`) en las transacciones del mes.

    Args:
        concepto (str): Nombre del producto o compra.
        valor_entrada (str | int): Monto total en pesos o jerga.
        cuotas (int): Número de cuotas (`1..36`).
        categoria (str | None): Categoría elegida o inferida automáticamente.
        usuario_id (int): Identificador del usuario autenticado.
        periodo (str | None): Periodo `'YYYY-MM'`.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Confirmación del registro realizado.
    """
    simulacion = simular_viabilidad_compra(
        concepto,
        valor_entrada,
        cuotas=cuotas,
        usuario_id=usuario_id,
        periodo=periodo,
        ruta_db=ruta_db,
    )
    monto_total = int(simulacion["monto_total"])
    valor_cuota = int(simulacion["valor_cuota"])
    cat_final = (
        categoria
        if categoria in CATEGORIAS_VALIDAS
        else str(simulacion["categoria_sugerida"])
    )

    if cuotas == 1:
        res_gasto = registrar_gasto_desde_texto(
            f"{concepto.strip()} {monto_total}",
            sub_etiqueta="Compra simulada",
            confirmado=True,
            usuario_id=usuario_id,
            periodo=periodo,
            ruta_db=ruta_db,
        )
        return {
            "registrado": True,
            "modalidad": "contado",
            "mensaje": (
                f"Compra de contado '{concepto.strip()}' registrada por "
                f"{formatear_pesos(monto_total)}"
            ),
            "detalle": res_gasto,
        }

    cred_id = crear_credito(
        nombre=concepto.strip(),
        valor_cuota=valor_cuota,
        total_cuotas=cuotas,
        cuotas_pagadas=0,
        categoria=cat_final,
        usuario_id=usuario_id,
        ruta_db=ruta_db,
    )
    res_cuota = registrar_pago_cuota_credito(
        cred_id,
        usuario_id=usuario_id,
        periodo=periodo,
        ruta_db=ruta_db,
    )
    return {
        "registrado": True,
        "modalidad": "cuotas",
        "credito_id": cred_id,
        "mensaje": (
            f"Crédito '{concepto.strip()}' creado a {cuotas} cuotas y "
            f"primera cuota de {formatear_pesos(valor_cuota)} aplicada al mes"
        ),
        "detalle": res_cuota,
    }

"""Módulo de servicios y lógica de negocio para FinanzasPersonales-App.

Orquesta la captura en lenguaje natural de gastos e ingresos extra (HU-01,
HU-02, HU-09), clasificación temática (HU-03), cálculo de balance y métricas
del dashboard (HU-04, HU-05), alertas preventivas de sobregiro y consumo mayor
al 50% (HU-06), filtrado por categoría (HU-07), exportación CSV (HU-08),
aplicación de gastos fijos mensuales (HU-10) y pago de cuotas de créditos (HU-11).
"""

import csv
from datetime import datetime
import io
from pathlib import Path
import re
from typing import Any, Callable

from src.clasificador import clasificar_gasto, extraer_concepto
from src.database import (
    RUTA_DB_DEFECTO,
    incrementar_cuota_credito,
    insertar_ingreso_extra,
    insertar_transaccion,
    listar_creditos,
    listar_gastos_fijos,
    listar_ingresos_extra,
    listar_transacciones,
    obtener_presupuesto,
)
from src.parser_montos import MENSAJE_MONTO_AMBIGUO, extraer_monto

MENSAJE_GASTO_REGISTRADO: str = "Gasto registrado exitosamente"
MENSAJE_INGRESO_REGISTRADO: str = "Ingreso extra registrado exitosamente"
MENSAJE_GASTO_FIJO_APLICADO: str = "Gasto fijo aplicado al mes exitosamente"
MENSAJE_CUOTA_REGISTRADA: str = "Pago de cuota registrado exitosamente"
MENSAJE_SIN_MONTO_VALIDO: str = (
    "No se detectó un valor monetario válido. Ingrese el monto del gasto"
)
MENSAJE_PRESUPUESTO_NO_ESTABLECIDO: str = (
    "Presupuesto mensual no establecido. "
    "Ingrese su presupuesto en la barra lateral para calcular su saldo"
)
MENSAJE_ALERTA_SOBREGIRO: str = (
    "[ALERTA DE SOBREGIRO] Este gasto supera su saldo restante"
)
MENSAJE_CSV_VACIO: str = (
    "Operación no disponible: No existen transacciones para exportar"
)

UMBRAL_GASTO_DESPROPORCIONADO: float = 0.5
ENCABEZADOS_CSV: tuple[str, ...] = (
    "id",
    "fecha",
    "concepto",
    "monto",
    "categoria",
)
MESES_ESPANOL: dict[int, str] = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

PATRON_INDICADOR_MONTO_O_AMBIGUEDAD: re.Pattern[str] = re.compile(
    r"(\d|\b(?:media|medio|un\s+par\s+de|varias|algunas|lucas?|mil)\b)",
    re.IGNORECASE,
)
PATRON_FRASE_INGRESO: re.Pattern[str] = re.compile(
    r"^(?:ingreso(?:\s+extra)?|abono|abon[eé]|me\s+entraron|me\s+pagaron|"
    r"recib[ií]|gan[eé])\b",
    re.IGNORECASE,
)
PATRON_PREFIJO_INGRESO: re.Pattern[str] = re.compile(
    r"^(?:ingreso(?:\s+extra)?|abono|abon[eé]|me\s+entraron|me\s+pagaron|"
    r"recib[ií]|gan[eé])\s*(?:de\s+|por\s+)?",
    re.IGNORECASE,
)


def formatear_pesos(valor: int | None) -> str:
    """Formatea un valor entero en pesos colombianos con separador de miles (.).

    Args:
        valor (int | None): Monto entero en COP (positivo, negativo o `None`).

    Returns:
        str: Representación formateada (ej. `'$600.000'`, `'-$15.000'` o `'?'`).
    """
    if valor is None:
        return "?"
    signo = "-" if valor < 0 else ""
    cifras = f"{abs(valor):,}".replace(",", ".")
    return f"{signo}${cifras}"


def _calcular_porcentaje_truncado(numerador: int, denominador: int) -> float:
    """Calcula el porcentaje con un decimal truncado según criterios de HU-04 y HU-06.

    Args:
        numerador (int): Monto parcial o acumulado.
        denominador (int): Presupuesto o capacidad mensual total (`> 0`).

    Returns:
        float: Porcentaje con un decimal (ej. `220000 / 600000` -> `36.6`).
    """
    if denominador <= 0:
        return 0.0
    return int((numerador / denominador) * 1000) / 10.0


def es_frase_ingreso_extra(texto: str) -> bool:
    """Detecta si una frase en lenguaje natural describe un ingreso extra o abono.

    Args:
        texto (str): Frase ingresada por el usuario.

    Returns:
        bool: `True` si inicia con verbos/indicadores de ingreso (`'me entraron'`,
            `'ingreso'`, `'abono'`, `'me pagaron'`).
    """
    if not isinstance(texto, str) or not texto.strip():
        return False
    return bool(PATRON_FRASE_INGRESO.search(texto.strip()))


def registrar_ingreso_desde_texto(
    texto: str,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Procesa y registra un ingreso extra o abono en lenguaje natural (HU-09).

    Extrae el monto usando el parser coloquial (`extraer_monto`), limpia el
    concepto y almacena el abono en la tabla `ingresos_extra`, incrementando
    el saldo disponible del mes.

    Args:
        texto (str): Descripción del ingreso (ej. `'me entraron 1.200.000 de trabajo'`).
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Resultado con `registrado`, `tipo_alerta`, `mensaje`
            e `ingreso`.

    Raises:
        ValueError: Si no se detecta un monto válido o si el monto es ambiguo.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    if len(texto) <= 280 and not PATRON_INDICADOR_MONTO_O_AMBIGUEDAD.search(texto):
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    monto = extraer_monto(texto)
    texto_sin_prefijo = PATRON_PREFIJO_INGRESO.sub("", texto.strip()).strip()
    concepto_base = extraer_concepto(texto_sin_prefijo or texto)
    if concepto_base == "Gasto registrado":
        concepto_base = "Ingreso extra"

    ingreso_id = insertar_ingreso_extra(
        concepto=concepto_base,
        monto=monto,
        ruta_db=ruta_db,
    )

    return {
        "registrado": True,
        "requiere_confirmacion": False,
        "tipo_operacion": "ingreso",
        "tipo_alerta": "exito",
        "mensaje": MENSAJE_INGRESO_REGISTRADO,
        "alerta_sobregiro": None,
        "ingreso": {
            "id": ingreso_id,
            "concepto": concepto_base,
            "monto": monto,
        },
    }


def registrar_gasto_desde_texto(
    texto: str,
    *,
    confirmado: bool = False,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    cliente_llm: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Procesa, valida y registra un gasto ingresado en lenguaje natural.

    Args:
        texto (str): Frase cotidiana ingresada por el usuario.
        confirmado (bool): `True` si el usuario ya confirmó un gasto mayor al 50%.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.
        cliente_llm (Callable[[dict[str, Any]], str] | None): Cliente LLM opcional.

    Returns:
        dict[str, Any]: Resultado de la operación con estado, alertas y transacción.

    Raises:
        ValueError: Si no se detecta un monto válido (HU-01 Esc. 2) o si el monto
            es ambiguo (HU-02 Esc. 2).
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    if len(texto) <= 280 and not PATRON_INDICADOR_MONTO_O_AMBIGUEDAD.search(texto):
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    monto = extraer_monto(texto)
    concepto = extraer_concepto(texto)
    categoria, es_ambiguo = clasificar_gasto(texto, cliente_llm=cliente_llm)

    presupuesto = obtener_presupuesto(ruta_db)

    if (
        presupuesto is not None
        and not confirmado
        and monto > (presupuesto * UMBRAL_GASTO_DESPROPORCIONADO)
    ):
        porcentaje_gasto = _calcular_porcentaje_truncado(monto, presupuesto)
        mensaje_confirmacion = (
            f"Atención: Este gasto representa el {porcentaje_gasto:.1f}% de su "
            "presupuesto mensual. ¿Desea confirmar el registro? "
            "(Confirmar / Cancelar)"
        )
        return {
            "registrado": False,
            "requiere_confirmacion": True,
            "tipo_alerta": "confirmacion",
            "mensaje": mensaje_confirmacion,
            "alerta_sobregiro": None,
            "porcentaje_presupuesto": porcentaje_gasto,
            "transaccion": {
                "concepto": concepto,
                "monto": monto,
                "categoria": categoria,
                "es_ambiguo": es_ambiguo,
            },
        }

    tx_id = insertar_transaccion(
        concepto=concepto,
        monto=monto,
        categoria=categoria,
        es_ambiguo=es_ambiguo,
        ruta_db=ruta_db,
    )

    total_gastado = sum(
        int(item["monto"]) for item in listar_transacciones(ruta_db=ruta_db)
    )
    total_ingresos = sum(
        int(item["monto"]) for item in listar_ingresos_extra(ruta_db=ruta_db)
    )

    alerta_sobregiro: str | None = None
    if presupuesto is not None and (presupuesto + total_ingresos - total_gastado) < 0:
        alerta_sobregiro = MENSAJE_ALERTA_SOBREGIRO

    return {
        "registrado": True,
        "requiere_confirmacion": False,
        "tipo_alerta": "exito",
        "mensaje": MENSAJE_GASTO_REGISTRADO,
        "alerta_sobregiro": alerta_sobregiro,
        "porcentaje_presupuesto": (
            _calcular_porcentaje_truncado(monto, presupuesto)
            if presupuesto is not None
            else 0.0
        ),
        "transaccion": {
            "id": tx_id,
            "concepto": concepto,
            "monto": monto,
            "categoria": categoria,
            "es_ambiguo": es_ambiguo,
        },
    }


def aplicar_gasto_fijo_al_mes(
    gasto_fijo_id: int,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Aplica un gasto fijo mensual registrándolo como transacción del mes (HU-10).

    Args:
        gasto_fijo_id (int): Identificador del gasto fijo recurrente.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Diccionario con confirmación y datos de la transacción.

    Raises:
        ValueError: Si el gasto fijo especificado no existe.
    """
    gastos_fijos = listar_gastos_fijos(ruta_db=ruta_db)
    seleccionado = next(
        (item for item in gastos_fijos if item["id"] == gasto_fijo_id),
        None,
    )
    if seleccionado is None:
        raise ValueError("El gasto fijo especificado no existe")

    concepto_tx = f"Gasto fijo: {seleccionado['nombre']}"
    tx_id = insertar_transaccion(
        concepto=concepto_tx,
        monto=int(seleccionado["monto"]),
        categoria=str(seleccionado["categoria"]),
        es_ambiguo=False,
        ruta_db=ruta_db,
    )

    return {
        "registrado": True,
        "tipo_alerta": "exito",
        "mensaje": MENSAJE_GASTO_FIJO_APLICADO,
        "transaccion": {
            "id": tx_id,
            "concepto": concepto_tx,
            "monto": int(seleccionado["monto"]),
            "categoria": str(seleccionado["categoria"]),
        },
    }


def registrar_pago_cuota_credito(
    credito_id: int,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Registra el pago de una cuota mensual de un crédito activo (HU-11).

    Incrementa en +1 las cuotas pagadas del crédito e inserta la transacción
    correspondiente en el historial de gastos del mes.

    Args:
        credito_id (int): Identificador del crédito.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Datos del crédito actualizado y la transacción creada.

    Raises:
        ValueError: Si el crédito no existe o ya tiene todas sus cuotas pagadas.
    """
    credito = incrementar_cuota_credito(credito_id, ruta_db=ruta_db)
    concepto_tx = (
        f"Cuota {credito['cuotas_pagadas']}/{credito['total_cuotas']}: "
        f"{credito['nombre']}"
    )
    tx_id = insertar_transaccion(
        concepto=concepto_tx,
        monto=int(credito["valor_cuota"]),
        categoria=str(credito["categoria"]),
        es_ambiguo=False,
        ruta_db=ruta_db,
    )

    return {
        "registrado": True,
        "tipo_alerta": "exito",
        "mensaje": MENSAJE_CUOTA_REGISTRADA,
        "credito": credito,
        "transaccion": {
            "id": tx_id,
            "concepto": concepto_tx,
            "monto": int(credito["valor_cuota"]),
            "categoria": str(credito["categoria"]),
        },
    }


def obtener_resumen_financiero(  # pylint: disable=too-many-locals
    categoria_filtro: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Calcula las métricas del panel web, ingresos extra, gastos fijos y créditos.

    Args:
        categoria_filtro (str | None): Categoría seleccionada para filtrar la tabla.
        ruta_db (str | Path): Ruta del archivo SQLite local.

    Returns:
        dict[str, Any]: Estado financiero consolidado del mes.
    """
    presupuesto = obtener_presupuesto(ruta_db)
    todas_transacciones = listar_transacciones(ruta_db=ruta_db)
    total_gastado = sum(int(item["monto"]) for item in todas_transacciones)

    ingresos_extra = listar_ingresos_extra(ruta_db=ruta_db)
    total_ingresos_extra = sum(int(item["monto"]) for item in ingresos_extra)

    gastos_fijos = listar_gastos_fijos(ruta_db=ruta_db)
    total_gastos_fijos = sum(int(item["monto"]) for item in gastos_fijos)

    creditos = listar_creditos(ruta_db=ruta_db)
    total_cuotas_activas = sum(
        int(item["valor_cuota"])
        for item in creditos
        if not item["pagado_completo"]
    )

    filtro_limpio = (
        categoria_filtro.strip()
        if isinstance(categoria_filtro, str) and categoria_filtro.strip()
        else "Todas"
    )
    transacciones_filtradas = (
        listar_transacciones(categoria=filtro_limpio, ruta_db=ruta_db)
        if filtro_limpio != "Todas"
        else todas_transacciones
    )
    subtotal_filtrado = sum(int(item["monto"]) for item in transacciones_filtradas)

    mensaje_filtro_vacio: str | None = None
    if filtro_limpio != "Todas" and len(transacciones_filtradas) == 0:
        mensaje_filtro_vacio = (
            "No se encontraron transacciones registradas para la categoría "
            f"'{filtro_limpio}' en este periodo"
        )

    datos_comunes: dict[str, Any] = {
        "ingresos_extra": ingresos_extra,
        "total_ingresos_extra": total_ingresos_extra,
        "total_ingresos_extra_fmt": f"+{formatear_pesos(total_ingresos_extra)}",
        "gastos_fijos": gastos_fijos,
        "total_gastos_fijos": total_gastos_fijos,
        "total_gastos_fijos_fmt": formatear_pesos(total_gastos_fijos),
        "creditos": creditos,
        "total_cuotas_activas": total_cuotas_activas,
        "total_cuotas_activas_fmt": formatear_pesos(total_cuotas_activas),
        "categoria_activa": filtro_limpio,
        "transacciones": transacciones_filtradas,
        "subtotal_filtrado": subtotal_filtrado,
        "subtotal_filtrado_fmt": formatear_pesos(subtotal_filtrado),
        "mensaje_filtro_vacio": mensaje_filtro_vacio,
    }

    if presupuesto is None:
        return {
            "presupuesto_configurado": False,
            "presupuesto_mensual": None,
            "presupuesto_fmt": "?",
            "capacidad_total": None,
            "capacidad_total_fmt": "?",
            "total_gastado": total_gastado,
            "total_gastado_fmt": formatear_pesos(total_gastado),
            "saldo_disponible": None,
            "saldo_disponible_fmt": "?",
            "porcentaje_consumo": 0.0,
            "porcentaje_barra": 0.0,
            "en_sobregiro": False,
            "mensaje_presupuesto": MENSAJE_PRESUPUESTO_NO_ESTABLECIDO,
            "alerta_sobregiro": None,
            **datos_comunes,
        }

    capacidad_total = presupuesto + total_ingresos_extra
    saldo_disponible = capacidad_total - total_gastado
    porcentaje_consumo = _calcular_porcentaje_truncado(total_gastado, capacidad_total)
    en_sobregiro = saldo_disponible < 0

    return {
        "presupuesto_configurado": True,
        "presupuesto_mensual": presupuesto,
        "presupuesto_fmt": formatear_pesos(presupuesto),
        "capacidad_total": capacidad_total,
        "capacidad_total_fmt": formatear_pesos(capacidad_total),
        "total_gastado": total_gastado,
        "total_gastado_fmt": formatear_pesos(total_gastado),
        "saldo_disponible": saldo_disponible,
        "saldo_disponible_fmt": (
            f"{formatear_pesos(saldo_disponible)} disponible"
            if not en_sobregiro
            else formatear_pesos(saldo_disponible)
        ),
        "porcentaje_consumo": porcentaje_consumo,
        "porcentaje_barra": min(porcentaje_consumo, 100.0),
        "en_sobregiro": en_sobregiro,
        "mensaje_presupuesto": None,
        "alerta_sobregiro": MENSAJE_ALERTA_SOBREGIRO if en_sobregiro else None,
        **datos_comunes,
    }


def exportar_transacciones_csv(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    mes_anio: str | None = None,
) -> tuple[str, str]:
    """Genera el archivo CSV estructurado con todas las transacciones (HU-08).

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite local.
        mes_anio (str | None): Sufijo opcional de periodo (ej. `'octubre_2026'`).

    Returns:
        tuple[str, str]: Tupla `(nombre_archivo, contenido_csv)` donde
            `nombre_archivo` sigue el patrón `'gastos_<mes>_<anio>.csv'` y
            `contenido_csv` incluye los encabezados oficiales del reporte.

    Raises:
        ValueError: Si la base de datos no contiene ninguna transacción registrada.
    """
    transacciones = listar_transacciones(ruta_db=ruta_db)
    if not transacciones:
        raise ValueError(MENSAJE_CSV_VACIO)

    transacciones_ordenadas = sorted(transacciones, key=lambda item: int(item["id"]))

    if mes_anio is None:
        ahora = datetime.now()
        nombre_mes = MESES_ESPANOL.get(ahora.month, "mes")
        periodo = f"{nombre_mes}_{ahora.year}"
    else:
        periodo = mes_anio.strip()

    nombre_archivo = f"gastos_{periodo}.csv"

    buffer_csv = io.StringIO()
    escritor = csv.writer(buffer_csv, lineterminator="\n")
    escritor.writerow(ENCABEZADOS_CSV)

    for tx in transacciones_ordenadas:
        escritor.writerow(
            [
                tx["id"],
                tx["fecha"],
                tx["concepto"],
                tx["monto"],
                tx["categoria"],
            ]
        )

    return nombre_archivo, buffer_csv.getvalue()


__all__ = [
    "MENSAJE_ALERTA_SOBREGIRO",
    "MENSAJE_CSV_VACIO",
    "MENSAJE_CUOTA_REGISTRADA",
    "MENSAJE_GASTO_FIJO_APLICADO",
    "MENSAJE_GASTO_REGISTRADO",
    "MENSAJE_INGRESO_REGISTRADO",
    "MENSAJE_MONTO_AMBIGUO",
    "MENSAJE_PRESUPUESTO_NO_ESTABLECIDO",
    "MENSAJE_SIN_MONTO_VALIDO",
    "aplicar_gasto_fijo_al_mes",
    "es_frase_ingreso_extra",
    "exportar_transacciones_csv",
    "formatear_pesos",
    "obtener_resumen_financiero",
    "registrar_gasto_desde_texto",
    "registrar_ingreso_desde_texto",
    "registrar_pago_cuota_credito",
]

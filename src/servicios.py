"""Módulo de servicios y lógica de negocio para FinanzasPersonales-App.

Orquesta la captura en lenguaje natural de gastos e ingresos extra (HU-01,
HU-02, HU-09), clasificación temática (HU-03), cálculo de balance mensual
con arrastre inteligente / rollover (HU-04, HU-05, HU-13), alertas preventivas
(HU-06), filtrado y búsqueda por categoría (HU-07, HU-14), exportación CSV
(HU-08), gastos fijos recurrentes (HU-10) y créditos a cuotas (HU-11).
"""

import calendar
import csv
from datetime import datetime
import io
from pathlib import Path
import re
from typing import Any, Callable

from src.clasificador import clasificar_gasto, extraer_concepto
from src.database import (
    CATEGORIAS_VALIDAS,
    RUTA_DB_DEFECTO,
    guardar_presupuesto,
    incrementar_cuota_credito,
    insertar_ingreso_extra,
    insertar_transaccion,
    listar_creditos,
    listar_gastos_fijos,
    listar_ingresos_extra,
    listar_transacciones,
    marcar_periodo_cerrado,
    obtener_datos_periodo,
    obtener_periodo_actual,
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
PATRON_PERIODO_YYYY_MM: re.Pattern[str] = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def formatear_pesos(valor: int | None) -> str:
    """Formatea un valor entero en pesos colombianos con separador de miles (.)."""
    if valor is None:
        return "?"
    signo = "-" if valor < 0 else ""
    cifras = f"{abs(valor):,}".replace(",", ".")
    return f"{signo}${cifras}"


def _validar_y_descomponer_periodo(periodo: str | None) -> tuple[int, int, str]:
    """Valida una cadena `'YYYY-MM'` y retorna `(anio, mes, periodo_normalizado)`."""
    periodo_limpio = (periodo or obtener_periodo_actual()).strip()
    if not PATRON_PERIODO_YYYY_MM.match(periodo_limpio):
        raise ValueError("El periodo debe tener el formato YYYY-MM")
    partes = periodo_limpio.split("-")
    return int(partes[0]), int(partes[1]), periodo_limpio


def calcular_periodo_siguiente(periodo: str | None = None) -> str:
    """Calcula el periodo `'YYYY-MM'` del mes inmediatamente siguiente (HU-13)."""
    anio, mes, _ = _validar_y_descomponer_periodo(periodo)
    if mes == 12:
        return f"{anio + 1:04d}-01"
    return f"{anio:04d}-{mes + 1:02d}"


def calcular_periodo_anterior(periodo: str | None = None) -> str:
    """Calcula el periodo `'YYYY-MM'` del mes inmediatamente anterior (HU-13)."""
    anio, mes, _ = _validar_y_descomponer_periodo(periodo)
    if mes == 1:
        return f"{anio - 1:04d}-12"
    return f"{anio:04d}-{mes - 1:02d}"


def formatear_etiqueta_periodo(periodo: str | None = None) -> str:
    """Convierte `'2026-11'` en una etiqueta legible como `'Noviembre 2026'`."""
    anio, mes, _ = _validar_y_descomponer_periodo(periodo)
    nombre_mes = MESES_ESPANOL.get(mes, "mes").capitalize()
    return f"{nombre_mes} {anio}"


def _calcular_dias_restantes_periodo(periodo: str | None = None) -> int:
    """Calcula los días restantes del mes activo (`>= 1`) para el presupuesto diario."""
    anio, mes, periodo_norm = _validar_y_descomponer_periodo(periodo)
    total_dias_mes = calendar.monthrange(anio, mes)[1]
    ahora = datetime.now()
    if periodo_norm == ahora.strftime("%Y-%m"):
        return max(total_dias_mes - ahora.day + 1, 1)
    return total_dias_mes


def _calcular_porcentaje_truncado(numerador: int, denominador: int) -> float:
    """Calcula el porcentaje con un decimal truncado según HU-04 y HU-06."""
    if denominador <= 0:
        return 0.0
    return int((numerador / denominador) * 1000) / 10.0


def es_frase_ingreso_extra(texto: str) -> bool:
    """Detecta si una frase en lenguaje natural describe un ingreso extra o abono."""
    if not isinstance(texto, str) or not texto.strip():
        return False
    return bool(PATRON_FRASE_INGRESO.search(texto.strip()))


def registrar_ingreso_desde_texto(
    texto: str,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Procesa y registra un ingreso extra o abono en lenguaje natural (HU-09)."""
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
        usuario_id=usuario_id,
        periodo=periodo,
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


def registrar_gasto_desde_texto(  # pylint: disable=too-many-arguments,too-many-locals
    texto: str,
    *,
    confirmado: bool = False,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    cliente_llm: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Procesa, valida y registra un gasto ingresado en lenguaje natural."""
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    if len(texto) <= 280 and not PATRON_INDICADOR_MONTO_O_AMBIGUEDAD.search(texto):
        raise ValueError(MENSAJE_SIN_MONTO_VALIDO)

    monto = extraer_monto(texto)
    concepto = extraer_concepto(texto)
    categoria, es_ambiguo = clasificar_gasto(texto, cliente_llm=cliente_llm)

    datos_periodo = obtener_datos_periodo(
        ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    presupuesto = datos_periodo["presupuesto_base"]

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
        usuario_id=usuario_id,
        periodo=periodo,
        ruta_db=ruta_db,
    )

    total_gastado = sum(
        int(item["monto"])
        for item in listar_transacciones(
            ruta_db=ruta_db,
            usuario_id=usuario_id,
            periodo=periodo,
        )
    )
    total_ingresos = sum(
        int(item["monto"])
        for item in listar_ingresos_extra(
            ruta_db=ruta_db,
            usuario_id=usuario_id,
            periodo=periodo,
        )
    )
    arrastre = int(datos_periodo["saldo_arrastrado"])
    meta_ahorro = int(datos_periodo["meta_ahorro"])

    alerta_sobregiro: str | None = None
    if (
        presupuesto is not None
        and (presupuesto + total_ingresos + arrastre - meta_ahorro - total_gastado) < 0
    ):
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
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Aplica un gasto fijo mensual registrándolo como transacción del mes (HU-10)."""
    gastos_fijos = listar_gastos_fijos(ruta_db=ruta_db, usuario_id=usuario_id)
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
        usuario_id=usuario_id,
        periodo=periodo,
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
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Registra el pago de una cuota mensual de un crédito del usuario (HU-11)."""
    credito = incrementar_cuota_credito(
        credito_id,
        ruta_db=ruta_db,
        usuario_id=usuario_id,
    )
    concepto_tx = (
        f"Cuota {credito['cuotas_pagadas']}/{credito['total_cuotas']}: "
        f"{credito['nombre']}"
    )
    tx_id = insertar_transaccion(
        concepto=concepto_tx,
        monto=int(credito["valor_cuota"]),
        categoria=str(credito["categoria"]),
        es_ambiguo=False,
        usuario_id=usuario_id,
        periodo=periodo,
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


def cerrar_y_avanzar_mes(
    *,
    usuario_id: int = 1,
    periodo_actual: str | None = None,
    nuevo_presupuesto_base: int | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Cierra el mes actual y arrastra el saldo positivo o negativo al siguiente.

    - Si el saldo final del mes es positivo (`> 0`), se arrastra como ganancia/ahorro
      a favor (`saldo_arrastrado > 0`).
    - Si el saldo final del mes es negativo (`< 0`), se arrastra como deuda/sobregiro
      pendiente (`saldo_arrastrado < 0`).

    Args:
        usuario_id (int): Identificador del usuario.
        periodo_actual (str | None): Periodo `'YYYY-MM'` por cerrar.
        nuevo_presupuesto_base (int | None): Presupuesto opcional para el nuevo mes.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Resumen del cierre con `periodo_cerrado`, `nuevo_periodo`,
            `saldo_arrastrado`, `tipo_arrastre` y `mensaje`.

    Raises:
        ValueError: Si el periodo actual no tiene presupuesto configurado.
    """
    _, _, periodo_origen = _validar_y_descomponer_periodo(periodo_actual)
    resumen = obtener_resumen_financiero(
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo_origen,
    )
    if not resumen["presupuesto_configurado"]:
        raise ValueError(
            "Debe configurar el presupuesto del mes actual antes de cerrar el periodo"
        )

    saldo_final = int(resumen["saldo_disponible"])
    presupuesto_heredado = (
        nuevo_presupuesto_base
        if nuevo_presupuesto_base is not None
        else int(resumen["presupuesto_mensual"])
    )
    meta_heredada = int(resumen["meta_ahorro"])
    periodo_destino = calcular_periodo_siguiente(periodo_origen)

    marcar_periodo_cerrado(
        usuario_id=usuario_id,
        periodo=periodo_origen,
        ruta_db=ruta_db,
    )
    guardar_presupuesto(
        presupuesto_heredado,
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo_destino,
        meta_ahorro=meta_heredada,
        saldo_arrastrado=saldo_final,
    )

    if saldo_final > 0:
        tipo_arrastre = "ganancia"
        detalle = f"Saldo a favor trasladado: +{formatear_pesos(saldo_final)}"
    elif saldo_final < 0:
        tipo_arrastre = "deuda"
        detalle = f"Saldo pendiente por cubrir: {formatear_pesos(saldo_final)}"
    else:
        tipo_arrastre = "equilibrio"
        detalle = "Mes cerrado en equilibrio ($0)"

    return {
        "periodo_cerrado": periodo_origen,
        "nuevo_periodo": periodo_destino,
        "saldo_arrastrado": saldo_final,
        "tipo_arrastre": tipo_arrastre,
        "mensaje": (
            f"Cierre de {formatear_etiqueta_periodo(periodo_origen)} completado. "
            f"{detalle}"
        ),
    }


def obtener_resumen_financiero(  # pylint: disable=too-many-locals
    categoria_filtro: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
    busqueda: str | None = None,
) -> dict[str, Any]:
    """Calcula las métricas del periodo, gráficas, arrastre y presupuesto diario."""
    _, _, periodo_activo = _validar_y_descomponer_periodo(periodo)
    datos_periodo = obtener_datos_periodo(
        ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    presupuesto = datos_periodo["presupuesto_base"]
    if presupuesto is None and usuario_id == 1 and periodo is None:
        presupuesto = obtener_presupuesto(ruta_db)

    meta_ahorro = int(datos_periodo["meta_ahorro"])
    saldo_arrastrado = int(datos_periodo["saldo_arrastrado"])

    todas_transacciones = listar_transacciones(
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    total_gastado = sum(int(item["monto"]) for item in todas_transacciones)

    ingresos_extra = listar_ingresos_extra(
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    total_ingresos_extra = sum(int(item["monto"]) for item in ingresos_extra)

    gastos_fijos = listar_gastos_fijos(ruta_db=ruta_db, usuario_id=usuario_id)
    total_gastos_fijos = sum(int(item["monto"]) for item in gastos_fijos)

    creditos = listar_creditos(ruta_db=ruta_db, usuario_id=usuario_id)
    total_cuotas_activas = sum(
        int(item["valor_cuota"])
        for item in creditos
        if not item["pagado_completo"]
    )

    gastos_por_categoria: dict[str, int] = {cat: 0 for cat in CATEGORIAS_VALIDAS}
    for item in todas_transacciones:
        cat_tx = str(item["categoria"])
        if cat_tx in gastos_por_categoria:
            gastos_por_categoria[cat_tx] += int(item["monto"])

    filtro_limpio = (
        categoria_filtro.strip()
        if isinstance(categoria_filtro, str) and categoria_filtro.strip()
        else "Todas"
    )
    transacciones_filtradas = listar_transacciones(
        categoria=filtro_limpio if filtro_limpio != "Todas" else None,
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
        busqueda=busqueda,
    )
    subtotal_filtrado = sum(int(item["monto"]) for item in transacciones_filtradas)

    mensaje_filtro_vacio: str | None = None
    if filtro_limpio != "Todas" and len(transacciones_filtradas) == 0:
        mensaje_filtro_vacio = (
            "No se encontraron transacciones registradas para la categoría "
            f"'{filtro_limpio}' en este periodo"
        )

    dias_restantes = _calcular_dias_restantes_periodo(periodo_activo)
    signo_arrastre = "+" if saldo_arrastrado > 0 else ""

    datos_comunes: dict[str, Any] = {
        "periodo_activo": periodo_activo,
        "etiqueta_periodo": formatear_etiqueta_periodo(periodo_activo),
        "periodo_anterior": calcular_periodo_anterior(periodo_activo),
        "periodo_siguiente": calcular_periodo_siguiente(periodo_activo),
        "meta_ahorro": meta_ahorro,
        "meta_ahorro_fmt": formatear_pesos(meta_ahorro),
        "saldo_arrastrado": saldo_arrastrado,
        "saldo_arrastrado_fmt": f"{signo_arrastre}{formatear_pesos(saldo_arrastrado)}",
        "ingresos_extra": ingresos_extra,
        "total_ingresos_extra": total_ingresos_extra,
        "total_ingresos_extra_fmt": f"+{formatear_pesos(total_ingresos_extra)}",
        "gastos_fijos": gastos_fijos,
        "total_gastos_fijos": total_gastos_fijos,
        "total_gastos_fijos_fmt": formatear_pesos(total_gastos_fijos),
        "creditos": creditos,
        "total_cuotas_activas": total_cuotas_activas,
        "total_cuotas_activas_fmt": formatear_pesos(total_cuotas_activas),
        "gastos_por_categoria": gastos_por_categoria,
        "dias_restantes_mes": dias_restantes,
        "categoria_activa": filtro_limpio,
        "busqueda_activa": busqueda.strip() if isinstance(busqueda, str) else "",
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
            "presupuesto_diario_sugerido": 0,
            "presupuesto_diario_fmt": "?",
            "porcentaje_consumo": 0.0,
            "porcentaje_barra": 0.0,
            "en_sobregiro": False,
            "mensaje_presupuesto": MENSAJE_PRESUPUESTO_NO_ESTABLECIDO,
            "alerta_sobregiro": None,
            **datos_comunes,
        }

    capacidad_total = presupuesto + total_ingresos_extra + saldo_arrastrado
    saldo_disponible = capacidad_total - meta_ahorro - total_gastado
    base_porcentaje = max(capacidad_total - meta_ahorro, 1)
    porcentaje_consumo = _calcular_porcentaje_truncado(total_gastado, base_porcentaje)
    en_sobregiro = saldo_disponible < 0
    diario_sugerido = max(0, saldo_disponible // dias_restantes)

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
        "presupuesto_diario_sugerido": diario_sugerido,
        "presupuesto_diario_fmt": f"{formatear_pesos(diario_sugerido)} / día",
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
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
) -> tuple[str, str]:
    """Genera el archivo CSV estructurado con las transacciones del usuario (HU-08)."""
    transacciones = listar_transacciones(
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    if not transacciones:
        raise ValueError(MENSAJE_CSV_VACIO)

    transacciones_ordenadas = sorted(transacciones, key=lambda item: int(item["id"]))

    if mes_anio is None:
        ahora = datetime.now()
        nombre_mes = MESES_ESPANOL.get(ahora.month, "mes")
        periodo_nombre = f"{nombre_mes}_{ahora.year}"
    else:
        periodo_nombre = mes_anio.strip()

    nombre_archivo = f"gastos_{periodo_nombre}.csv"

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
    "calcular_periodo_anterior",
    "calcular_periodo_siguiente",
    "cerrar_y_avanzar_mes",
    "es_frase_ingreso_extra",
    "exportar_transacciones_csv",
    "formatear_etiqueta_periodo",
    "formatear_pesos",
    "obtener_resumen_financiero",
    "registrar_gasto_desde_texto",
    "registrar_ingreso_desde_texto",
    "registrar_pago_cuota_credito",
]

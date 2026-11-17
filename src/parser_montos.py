"""Módulo para la extracción y normalización de montos monetarios (HU-02)."""

import re


def extraer_monto(texto: str) -> int:
    """Extrae y normaliza un monto monetario en pesos colombianos desde un texto.

    Args:
        texto (str): Descripción del gasto en lenguaje natural o cifra numérica.

    Returns:
        int: Valor monetario entero positivo normalizado en COP.

    Raises:
        ValueError: Si el monto es ambiguo o no contiene cifras numéricas válidas.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(
            "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        )

    texto_limpio = texto.strip().lower()

    if re.search(r"\b(media|medio|un\s+par\s+de|varias|algunas)\b", texto_limpio):
        raise ValueError(
            "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        )

    coincidencias = re.findall(
        r"(?<!\d)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(lucas?|mil)\b)?",
        texto_limpio,
    )

    if len(coincidencias) != 1:
        raise ValueError(
            "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        )

    cifra_str, multiplicador = coincidencias[0]
    valor_base = int(cifra_str.replace(".", ""))

    if valor_base <= 0:
        raise ValueError(
            "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        )

    if multiplicador in ("luca", "lucas", "mil"):
        return valor_base * 1000

    return valor_base

"""Módulo para la extracción y normalización de montos monetarios (HU-02).

Provee funciones deterministas basadas en expresiones regulares para convertir
descripciones de gastos en lenguaje natural o jerga colombiana a valores enteros
en pesos colombianos (COP).
"""

import re

MENSAJE_MONTO_AMBIGUO: str = (
    "Monto ambiguo. Por favor indique el valor en cifras numéricas"
)
FACTOR_MILES: int = 1000
MULTIPLICADORES_MILES: frozenset[str] = frozenset({"luca", "lucas", "mil"})

PATRON_CUANTIFICADORES_AMBIGUOS: re.Pattern[str] = re.compile(
    r"\b(media|medio|un\s+par\s+de|varias|algunas)\b"
)
PATRON_MONTO_COLOQUIAL: re.Pattern[str] = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(lucas?|mil)\b)?"
)


def _normalizar_texto_entrada(texto: str) -> str:
    """Valida y normaliza la cadena de entrada a minúsculas sin espacios extremos.

    Args:
        texto (str): Cadena original ingresada por el usuario.

    Returns:
        str: Texto limpio y en minúsculas listo para el análisis léxico.

    Raises:
        ValueError: Si la entrada no es un texto válido, está vacía o contiene
            cuantificadores fraccionarios/ambiguos sin cifra numérica.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    texto_normalizado = texto.strip().lower()

    if PATRON_CUANTIFICADORES_AMBIGUOS.search(texto_normalizado):
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    return texto_normalizado


def _extraer_componentes_monto(texto_normalizado: str) -> tuple[str, str]:
    """Extrae la cifra numérica y el multiplicador coloquial único del texto.

    Args:
        texto_normalizado (str): Texto previamente validado y en minúsculas.

    Returns:
        tuple[str, str]: Tupla con la cifra numérica en texto y el multiplicador
            coloquial encontrado (o cadena vacía si no aplica).

    Raises:
        ValueError: Si no se encuentra exactamente un monto numérico en el texto.
    """
    coincidencias = PATRON_MONTO_COLOQUIAL.findall(texto_normalizado)

    if len(coincidencias) != 1:
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    cifra_str, multiplicador = coincidencias[0]
    return cifra_str, multiplicador


def _calcular_valor_entero(cifra_str: str, multiplicador: str) -> int:
    """Convierte la cifra extraída y su multiplicador en un monto entero en COP.

    Args:
        cifra_str (str): Representación textual del número (con o sin puntos de mil).
        multiplicador (str): Término coloquial asociado ('luca', 'lucas', 'mil' o '').

    Returns:
        int: Valor monetario entero positivo en pesos colombianos.

    Raises:
        ValueError: Si el valor numérico resultante es menor o igual a cero.
    """
    valor_base = int(cifra_str.replace(".", ""))

    if valor_base <= 0:
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    if multiplicador in MULTIPLICADORES_MILES:
        return valor_base * FACTOR_MILES

    return valor_base


def extraer_monto(texto: str) -> int:
    """Extrae y normaliza un monto monetario en pesos colombianos desde un texto.

    Args:
        texto (str): Descripción del gasto en lenguaje natural o cifra numérica.

    Returns:
        int: Valor monetario entero positivo normalizado en COP.

    Raises:
        ValueError: Si el monto es ambiguo o no contiene cifras numéricas válidas.
    """
    texto_normalizado = _normalizar_texto_entrada(texto)
    cifra_str, multiplicador = _extraer_componentes_monto(texto_normalizado)
    return _calcular_valor_entero(cifra_str, multiplicador)

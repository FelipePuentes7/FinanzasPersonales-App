"""Módulo para la extracción y normalización de montos monetarios (HU-02).

Provee funciones deterministas basadas en expresiones regulares para convertir
descripciones de gastos en lenguaje natural o jerga colombiana a valores enteros
en pesos colombianos (COP), aplicando controles de validación de entrada y
mitigación de abuso (longitud máxima y rechazo de montos negativos).
"""

import re

MENSAJE_MONTO_AMBIGUO: str = (
    "Monto ambiguo. Por favor indique el valor en cifras numéricas"
)
FACTOR_MILES: int = 1000
LONGITUD_MAXIMA_TEXTO: int = 280
MULTIPLICADORES_MILES: frozenset[str] = frozenset({"luca", "lucas", "mil"})

PATRON_CUANTIFICADORES_AMBIGUOS: re.Pattern[str] = re.compile(
    r"\b(media|medio|un\s+par\s+de|varias|algunas)\b"
)
PATRON_SIGNO_NEGATIVO: re.Pattern[str] = re.compile(r"(?<!\w)-\s*\d")
PATRON_MONTO_COLOQUIAL: re.Pattern[str] = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(lucas?|mil)\b)?"
)


def _normalizar_texto_entrada(texto: str) -> str:
    """Valida, acota y normaliza la cadena de entrada a minúsculas sin espacios.

    Verifica que la entrada sea una cadena no vacía, que no supere el límite
    máximo de caracteres permitido (`LONGITUD_MAXIMA_TEXTO`) para prevenir
    consumo excesivo de recursos (DoS), y que no contenga signos negativos
    adheridos a cifras ni cuantificadores fraccionarios ambiguos.

    Args:
        texto (str): Cadena original ingresada por el usuario con la descripción
            del gasto.

    Returns:
        str: Texto limpio y en minúsculas listo para la extracción léxica.

    Raises:
        ValueError: Si la entrada no es de tipo `str`, está vacía, excede
            `LONGITUD_MAXIMA_TEXTO`, incluye cifras negativas o contiene
            cuantificadores ambiguos sin valor numérico claro.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    if len(texto) > LONGITUD_MAXIMA_TEXTO:
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    texto_normalizado = texto.strip().lower()

    if PATRON_SIGNO_NEGATIVO.search(texto_normalizado):
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    if PATRON_CUANTIFICADORES_AMBIGUOS.search(texto_normalizado):
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    return texto_normalizado


def _extraer_componentes_monto(texto_normalizado: str) -> tuple[str, str]:
    """Extrae la cifra numérica única y el multiplicador coloquial del texto.

    Busca todas las coincidencias numéricas y sus posibles sufijos coloquiales
    ('luca', 'lucas', 'mil') dentro del texto normalizado, exigiendo que exista
    exactamente un monto para evitar ambigüedad.

    Args:
        texto_normalizado (str): Texto previamente validado y en minúsculas.

    Returns:
        tuple[str, str]: Tupla `(cifra_str, multiplicador)` donde `cifra_str` es
            la representación textual del número y `multiplicador` es el término
            coloquial en minúsculas (o cadena vacía `""` si no se especificó).

    Raises:
        ValueError: Si no se encuentra ningún número o si existen múltiples
            cifras numéricas que hacen ambiguo el monto del gasto.
    """
    coincidencias = PATRON_MONTO_COLOQUIAL.findall(texto_normalizado)

    if len(coincidencias) != 1:
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    cifra_str, multiplicador = coincidencias[0]
    return cifra_str, multiplicador


def _calcular_valor_entero(cifra_str: str, multiplicador: str) -> int:
    """Convierte la cifra extraída y su multiplicador en un monto entero en COP.

    Elimina los puntos separadores de miles de la cifra textual, convierte el
    resultado a entero, verifica que sea estrictamente positivo y aplica el
    factor `FACTOR_MILES` cuando el multiplicador pertenece a
    `MULTIPLICADORES_MILES`.

    Args:
        cifra_str (str): Representación textual del número (con o sin puntos
            separadores de miles).
        multiplicador (str): Término coloquial asociado ('luca', 'lucas',
            'mil' o cadena vacía `""`).

    Returns:
        int: Valor monetario entero estrictamente positivo (`> 0`) en pesos
            colombianos (COP).

    Raises:
        ValueError: Si el valor numérico convertido es menor o igual a cero.
    """
    valor_base = int(cifra_str.replace(".", ""))

    if valor_base <= 0:
        raise ValueError(MENSAJE_MONTO_AMBIGUO)

    if multiplicador in MULTIPLICADORES_MILES:
        return valor_base * FACTOR_MILES

    return valor_base


def extraer_monto(texto: str) -> int:
    """Extrae y normaliza un monto monetario en pesos colombianos desde un texto.

    Orquesta la validación de seguridad y longitud de la entrada, la extracción
    léxica mediante expresiones regulares deterministas y el cálculo del valor
    entero en pesos colombianos (COP) según el contrato de la historia `HU-02`.

    Args:
        texto (str): Descripción del gasto en lenguaje natural, jerga monetaria
            colombiana ('luca', 'lucas', 'mil') o cifra numérica con o sin
            punto separador de miles.

    Returns:
        int: Valor monetario entero positivo (`> 0`) normalizado en COP.

    Raises:
        ValueError: Si `texto` no es una cadena válida, supera la longitud
            máxima permitida (`280` caracteres), contiene montos negativos o
            cero, o si el monto es ambiguo / carece de cifras numéricas.
    """
    texto_normalizado = _normalizar_texto_entrada(texto)
    cifra_str, multiplicador = _extraer_componentes_monto(texto_normalizado)
    return _calcular_valor_entero(cifra_str, multiplicador)

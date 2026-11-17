"""Módulo para la extracción y normalización de montos monetarios (HU-02)."""


def extraer_monto(texto: str) -> int:
    """Extrae y normaliza un monto monetario en pesos colombianos desde un texto.

    Args:
        texto (str): Descripción del gasto en lenguaje natural o cifra numérica.

    Returns:
        int: Valor monetario entero positivo normalizado en COP.

    Raises:
        ValueError: Si el monto es ambiguo o no contiene cifras numéricas válidas.
    """
    raise NotImplementedError("Función pendiente de implementación (Fase TDD: Rojo)")

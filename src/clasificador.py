"""Módulo de extracción de concepto, sanitización de privacidad y clasificación (HU-03).

Implementa la clasificación temática automática de gastos en las 5 categorías fijas
del sistema (`Transporte/Moto`, `Alimentación`, `Estudio`, `Ocio`, `Gastos Varios`),
con sanitización de datos personales identificables (RNF-03) y modo fallback offline
determinista ante ausencia o fallo de conexión al modelo de lenguaje (RNF-02).
"""

import logging
import re
from typing import Any, Callable
import unicodedata

from src.database import CATEGORIAS_VALIDAS

LOGGER = logging.getLogger(__name__)
CATEGORIA_DEFECTO: str = "Gastos Varios"

MAPA_PALABRAS_CLAVE: dict[str, tuple[str, ...]] = {
    "Transporte/Moto": (
        "moto",
        "motora",
        "gasolina",
        "tanquee",
        "tanquear",
        "tanqueada",
        "aceite",
        "llanta",
        "llantas",
        "repuesto",
        "repuestos",
        "freno",
        "frenos",
        "kit de arrastre",
        "cadena",
        "casco",
        "soat",
        "mecanico",
        "parqueadero",
        "peaje",
        "bus",
        "transporte",
        "pasaje",
        "pasajes",
        "taxi",
        "uber",
        "didi",
        "transmilenio",
    ),
    "Alimentación": (
        "almuerzo",
        "desayuno",
        "cena",
        "comida",
        "corriente",
        "corrientazo",
        "restaurante",
        "cafe",
        "tinto",
        "empanada",
        "empanadas",
        "arepa",
        "mercado",
        "supermercado",
        "panaderia",
        "dulce",
        "dulces",
        "gaseosa",
        "jugo",
        "hamburguesa",
        "pizza",
        "pollo",
        "fruta",
        "mecato",
    ),
    "Estudio": (
        "fotocopia",
        "fotocopias",
        "impresion",
        "impresiones",
        "libro",
        "libros",
        "cuaderno",
        "cuadernos",
        "taller de sistemas",
        "sistemas",
        "universidad",
        "semestre",
        "matricula",
        "curso",
        "papeleria",
        "lapicero",
        "parcial",
        "tesis",
        "laboratorio",
        "estudio",
    ),
    "Ocio": (
        "cine",
        "pelicula",
        "videojuego",
        "juego",
        "concierto",
        "bar",
        "cerveza",
        "salida",
        "fiesta",
        "netflix",
        "spotify",
        "paseo",
        "futbol",
        "cancha",
        "chaqueta",
        "camiseta",
        "ropa",
        "regalo",
        "ocio",
    ),
}

PATRON_CEDULA_ID: re.Pattern[str] = re.compile(
    r"\b(?:c\.?c\.?|c[eé]dula|nit|documento|id)\s*[:#-]?\s*\d[\d\.\-]{5,14}\b",
    re.IGNORECASE,
)
PATRON_DIRECCION_FISICA: re.Pattern[str] = re.compile(
    r"\b(?:calle|carrera|cra\.?|cll\.?|avenida|av\.?|diagonal|transversal)\s+"
    r"\d+[a-z]?\s*(?:#|no\.?|n[uú]mero)\s*\d+[a-z]?(?:\s*-\s*\d+)?\b",
    re.IGNORECASE,
)
PATRON_NOMBRE_PROPIO: re.Pattern[str] = re.compile(
    r"\b(?:a\s+nombre\s+de|cliente|usuario|se[ñn]or(?:a)?|sr\.?|sra\.?)\s+"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+",
)
PATRON_MONTO_EN_FRASE: re.Pattern[str] = re.compile(
    r"(?<!\d)\$?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(?:lucas?|mil|pesos|cop)\b)?",
    re.IGNORECASE,
)
PATRON_VERBOS_INICIALES: re.Pattern[str] = re.compile(
    r"^(?:gast[eé]|pagu[eé]|compr[eé]|di|met[ií])\s+(?:en\s+|de\s+|por\s+|para\s+)?",
    re.IGNORECASE,
)
PATRON_PREPOSICION_SUELTA: re.Pattern[str] = re.compile(
    r"^(?:de|en|por|para)\s+|(?:\s+(?:de|en|por|para))$",
    re.IGNORECASE,
)


def _quitar_tildes(texto: str) -> str:
    """Elimina signos diacríticos (tildes) conservando letras base para búsqueda.

    Args:
        texto (str): Cadena en minúsculas.

    Returns:
        str: Cadena normalizada sin acentos gráficos.
    """
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(
        caracter
        for caracter in normalizado
        if unicodedata.category(caracter) != "Mn"
    )


def sanitizar_texto_privacidad(texto: str) -> str:
    """Anonimiza nombres completos, números de cédula y direcciones físicas (RNF-03).

    Args:
        texto (str): Frase original ingresada por el usuario.

    Returns:
        str: Frase anonimizada sin datos personales identificables (PII).

    Raises:
        ValueError: Si `texto` no es una cadena válida o está vacía.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("El texto por sanitizar no puede estar vacío")

    resultado = PATRON_CEDULA_ID.sub("[ID_ANONIMIZADO]", texto.strip())
    resultado = PATRON_DIRECCION_FISICA.sub("[UBICACION_ANONIMIZADA]", resultado)
    resultado = PATRON_NOMBRE_PROPIO.sub("[NOMBRE_ANONIMIZADO]", resultado)
    return resultado


def construir_payload_llm(texto: str) -> dict[str, Any]:
    """Construye el payload JSON seguro para consulta a un modelo LLM (RNF-03).

    Garantiza que únicamente se transmita la frase anonimizada del gasto y el
    catálogo cerrado de categorías, sin incluir identificadores, nombres ni
    ubicaciones físicas del usuario.

    Args:
        texto (str): Frase del gasto ingresada por el usuario.

    Returns:
        dict[str, Any]: Diccionario listo para serializar con `frase_anonimizada`
            y `categorias_permitidas`.

    Raises:
        ValueError: Si `texto` está vacío o no es de tipo `str`.
    """
    frase_segura = sanitizar_texto_privacidad(texto)
    return {
        "frase_anonimizada": frase_segura,
        "categorias_permitidas": list(CATEGORIAS_VALIDAS),
    }


def extraer_concepto(texto: str) -> str:
    """Extrae y formatea el concepto descriptivo del gasto a partir de la frase (HU-01).

    Remueve la cifra monetaria y sus sufijos coloquiales ('lucas', 'mil'), limpia
    verbos auxiliares iniciales ('gasté', 'pagué') y preposiciones sueltas, y
    capitaliza la primera letra del concepto resultante.

    Args:
        texto (str): Frase completa del gasto (ej. 'almuerzo corriente 14000').

    Returns:
        str: Concepto limpio y capitalizado (ej. 'Almuerzo corriente').

    Raises:
        ValueError: Si `texto` no es una cadena válida o está vacía.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("El texto del gasto no puede estar vacío")

    sin_monto = PATRON_MONTO_EN_FRASE.sub(" ", texto.strip())
    limpio = " ".join(sin_monto.split())
    limpio = PATRON_VERBOS_INICIALES.sub("", limpio).strip()
    limpio = PATRON_PREPOSICION_SUELTA.sub("", limpio).strip()
    limpio = " ".join(limpio.split())

    if not limpio:
        return "Gasto registrado"

    return limpio[0].upper() + limpio[1:]


def clasificar_gasto(
    texto: str,
    cliente_llm: Callable[[dict[str, Any]], str] | None = None,
) -> tuple[str, bool]:
    """Clasifica automáticamente un gasto en una de las 5 categorías fijas (HU-03).

    Si se provee `cliente_llm`, intenta clasificar enviando exclusivamente el
    payload anonimizado (`RNF-03`). Ante cualquier fallo de red, timeout o si no
    hay cliente LLM configurado, utiliza el clasificador semántico local offline
    (`RNF-02`). Si el concepto es ambiguo y no coincide con ninguna categoría
    específica, retorna `('Gastos Varios', True)` para resaltar la fila en la
    interfaz web (`HU-03` Escenario 2).

    Args:
        texto (str): Descripción del gasto en lenguaje natural.
        cliente_llm (Callable[[dict[str, Any]], str] | None): Función opcional
            que recibe el payload anonimizado y devuelve el nombre de la categoría.

    Returns:
        tuple[str, bool]: Tupla `(categoria, es_ambiguo)` donde `categoria`
            pertenece a `CATEGORIAS_VALIDAS` y `es_ambiguo` es `True` cuando el
            gasto cayó por defecto en `'Gastos Varios'` sin contexto reconocible.

    Raises:
        ValueError: Si `texto` no es una cadena válida o está vacía.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("El texto del gasto no puede estar vacío")

    if cliente_llm is not None:
        payload = construir_payload_llm(texto)
        try:
            respuesta_llm = cliente_llm(payload).strip()
            if (
                respuesta_llm in CATEGORIAS_VALIDAS
                and respuesta_llm != CATEGORIA_DEFECTO
            ):
                return respuesta_llm, False
        except (OSError, ValueError, RuntimeError) as error_llm:
            LOGGER.warning("Fallback offline activado tras fallo LLM: %s", error_llm)

    texto_plano = _quitar_tildes(texto.lower())

    for categoria, palabras_clave in MAPA_PALABRAS_CLAVE.items():
        for palabra in palabras_clave:
            patron = rf"\b{re.escape(palabra)}\b"
            if re.search(patron, texto_plano):
                return categoria, False

    return CATEGORIA_DEFECTO, True

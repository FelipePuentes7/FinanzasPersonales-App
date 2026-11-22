"""Pruebas unitarias para el módulo de normalización de montos (HU-02)."""

import pytest

from src.parser_montos import extraer_monto


def test_extraer_monto_coloquial_lucas() -> None:
    """Verifica la conversión de un caso normal con la jerga 'lucas'."""
    resultado = extraer_monto("20 lucas en almuerzo")
    assert resultado == 20000


def test_extraer_monto_mil_y_cifra_directa() -> None:
    """Verifica casos normales con la palabra 'mil' y cifras numéricas planas."""
    assert extraer_monto("12 mil en transporte") == 12000
    assert extraer_monto("14000") == 14000


def test_extraer_monto_limite_mayusculas_singular() -> None:
    """Verifica el caso límite con texto en mayúsculas y singular ('1 LUCA')."""
    resultado = extraer_monto("1 LUCA")
    assert resultado == 1000


def test_extraer_monto_limite_punto_separador_miles() -> None:
    """Verifica el caso límite de una cifra con punto separador de miles."""
    resultado = extraer_monto("4.500")
    assert resultado == 4500


def test_extraer_monto_error_monto_ambiguo_sin_cifras() -> None:
    """Verifica que una expresión ambigua sin dígitos lance el ValueError exacto."""
    mensaje_esperado = (
        r"^Monto ambiguo\. Por favor indique el valor en cifras numéricas$"
    )
    with pytest.raises(ValueError, match=mensaje_esperado):
        extraer_monto("gasté media luca en dulces")


def test_extraer_monto_abuso_monto_negativo() -> None:
    """Prueba de abuso (H-01): rechaza montos con signo negativo."""
    mensaje_esperado = (
        r"^Monto ambiguo\. Por favor indique el valor en cifras numéricas$"
    )
    with pytest.raises(ValueError, match=mensaje_esperado):
        extraer_monto("gasté -20 lucas en almuerzo")


def test_extraer_monto_abuso_longitud_excesiva() -> None:
    """Prueba de abuso (H-02): rechaza entradas masivas previniendo DoS."""
    mensaje_esperado = (
        r"^Monto ambiguo\. Por favor indique el valor en cifras numéricas$"
    )
    payload_masivo = "20 lucas " + ("a" * 500)
    with pytest.raises(ValueError, match=mensaje_esperado):
        extraer_monto(payload_masivo)

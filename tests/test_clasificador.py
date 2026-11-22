"""Pruebas unitarias para extracción de concepto, privacidad y clasificación (HU-03)."""

from typing import Any

from src.clasificador import (
    clasificar_gasto,
    construir_payload_llm,
    extraer_concepto,
    sanitizar_texto_privacidad,
)


def test_extraer_concepto_frases_cotidianas() -> None:
    """Verifica HU-01 Escenario 1: extrae concepto capitalizado sin el monto."""
    assert extraer_concepto("almuerzo corriente 14000") == "Almuerzo corriente"
    assert (
        extraer_concepto("20 lucas de gasolina para la moto")
        == "Gasolina para la moto"
    )
    assert (
        extraer_concepto("fotocopias taller de sistemas 4500")
        == "Fotocopias taller de sistemas"
    )


def test_clasificacion_automatica_categorias_principales() -> None:
    """Verifica HU-03 Escenario 1: inferencia correcta en las categorías fijas."""
    cat_estudio, ambiguo_1 = clasificar_gasto("fotocopias taller de sistemas 4500")
    assert cat_estudio == "Estudio"
    assert ambiguo_1 is False

    cat_moto, ambiguo_2 = clasificar_gasto("20 lucas de gasolina para la moto")
    assert cat_moto == "Transporte/Moto"
    assert ambiguo_2 is False

    cat_comida, ambiguo_3 = clasificar_gasto("almuerzo corriente 14000")
    assert cat_comida == "Alimentación"
    assert ambiguo_3 is False

    cat_ocio, ambiguo_4 = clasificar_gasto("compra chaqueta 95000")
    assert cat_ocio == "Ocio"
    assert ambiguo_4 is False


def test_clasificacion_concepto_ambiguo_gastos_varios() -> None:
    """Verifica HU-03 Escenario 2: concepto sin contexto va a Gastos Varios."""
    categoria, es_ambiguo = clasificar_gasto("pago asunto x 30000")
    assert categoria == "Gastos Varios"
    assert es_ambiguo is True


def test_fallback_offline_ante_fallo_de_red_llm() -> None:
    """Verifica RNF-02: si el cliente LLM falla, clasifica localmente sin bloquear."""

    def cliente_llm_caido(_payload: dict[str, Any]) -> str:
        raise ConnectionError("API LLM no disponible sin internet")

    categoria, es_ambiguo = clasificar_gasto(
        "reparación motora 250000",
        cliente_llm=cliente_llm_caido,
    )
    assert categoria == "Transporte/Moto"
    assert es_ambiguo is False


def test_privacidad_payload_llm_no_envia_datos_personales() -> None:
    """Verifica RNF-03: el payload al LLM anonimiza cédula, nombre y dirección."""
    frase_con_pii = (
        "almuerzo 15000 a nombre de Carlos Dussán "
        "CC 1020304050 en Calle 45 # 12-30"
    )
    texto_limpio = sanitizar_texto_privacidad(frase_con_pii)
    payload = construir_payload_llm(frase_con_pii)

    assert "Carlos Dussán" not in texto_limpio
    assert "1020304050" not in texto_limpio
    assert "Calle 45 # 12-30" not in texto_limpio
    assert "1020304050" not in payload["frase_anonimizada"]
    assert "Carlos Dussán" not in payload["frase_anonimizada"]

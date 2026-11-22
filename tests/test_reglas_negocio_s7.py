"""Suite formal de pruebas de caja negra para FinanzasPersonales-App (Semana 7).

Diseñada a partir de las reglas de negocio (oráculo) y tablas de casos de
`registro_pruebas.md`, aplicando particiones de equivalencia, valores límite,
tabla de decisión multicondición y datos sintéticos locales con casos difíciles.
"""

from pathlib import Path
from typing import Any
import pytest

from src.clasificador import clasificar_gasto, extraer_concepto
from src.database import (
    MENSAJE_PRESUPUESTO_INVALIDO,
    guardar_presupuesto,
    insertar_transaccion,
)
from src.parser_montos import MENSAJE_MONTO_AMBIGUO, extraer_monto
from src.servicios import (
    MENSAJE_ALERTA_SOBREGIRO,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
)


@pytest.fixture(name="dataset_gastos_sinteticos_locales")
def fixture_dataset_gastos_sinteticos_locales() -> dict[str, Any]:
    """Provee datos sintéticos 100% ficticios con contexto colombiano y casos difíciles.

    Incluye descripciones locales con tildes, letra 'ñ', apóstrofos, espacios
    redundantes, cadenas vacías y montos en cero, sin ningún dato personal real.

    Returns:
        dict[str, Any]: Conjunto estructurado de casos válidos e inválidos.
    """
    return {
        "contexto_ficticio": {
            "comercio": "Cafetería El Estudiante S.A.S. (Ficticia)",
            "nit_ficticio": "900.000.000-1",
            "telefono_ficticio": "300-000-0000",
        },
        "casos_validos_dificiles": [
            # Caso difícil con tildes múltiples y punto de mil
            (
                "alimentación: menú ejecutivo y café en cafetería 16.500",
                16500,
                "Alimentación",
                False,
                "Alimentación: menú ejecutivo y café en cafetería",
            ),
            # Caso difícil con letra 'ñ' (daño, piñón, cañería) y jerga 'lucas'
            (
                "reparación por daño de piñón y cañería de freno moto 48 lucas",
                48000,
                "Transporte/Moto",
                False,
                "Reparación por daño de piñón y cañería de freno moto",
            ),
            # Caso difícil con apóstrofo (D'Luxe) y jerga 'mil'
            (
                "almuerzo en restaurante D'Luxe Bistró 22 mil",
                22000,
                "Alimentación",
                False,
                "Almuerzo en restaurante D'Luxe Bistró",
            ),
            # Caso difícil con múltiples espacios al inicio, medio y final
            (
                "   fotocopias   taller   de   sistemas   4.500   ",
                4500,
                "Estudio",
                False,
                "Fotocopias taller de sistemas",
            ),
        ],
        "casos_invalidos_dificiles": [
            # Caso difícil: cadena completamente vacía
            "",
            # Caso difícil: solo espacios y tabulaciones
            "   \t  ",
            # Caso difícil: valor numérico en cero con texto con tilde y ñ
            "bono navideño de promoción 0",
        ],
    }


# ==============================================================================
# REGLA 1: extraer_monto(texto: str) -> int (HU-02)
# ==============================================================================


@pytest.mark.parametrize(
    ("texto_entrada", "monto_esperado"),
    [
        # Partición válida: modismo coloquial plural 'lucas' (20 * 1000)
        ("20 lucas de gasolina para la moto", 20000),
        # Partición válida: modismo coloquial 'mil' (15 * 1000)
        ("almuerzo ejecutivo 15 mil", 15000),
        # Partición válida: cifra con punto separador de miles
        ("fotocopias taller 4.500", 4500),
        # Partición válida: cifra entera directa sin modismo
        ("almuerzo corriente 14000", 14000),
        # Valor límite (borde inferior válido): primer entero positivo después de 0
        ("ajuste 1", 1),
        # Valor límite (borde inferior con modismo en mayúsculas): 1 * 1000
        ("1 LUCA", 1000),
        # Valor límite (borde superior de longitud): exactamente 280 caracteres
        ("1000 " + ("a" * 275), 1000),
    ],
)
def test_extraer_monto_particiones_y_limites_validos(
    texto_entrada: str,
    monto_esperado: int,
) -> None:
    """Verifica particiones válidas y límites inferiores/superiores de extraer_monto."""
    assert extraer_monto(texto_entrada) == monto_esperado


@pytest.mark.parametrize(
    "texto_invalido",
    [
        # Valor límite (borde inferior inválido): último entero no positivo (0)
        "descuento 0",
        # Valor límite (borde inferior con modismo en cero): 0 lucas
        "0 lucas en parqueadero",
        # Valor límite (borde negativo inmediato): primer entero negativo (-1)
        "ajuste -1",
        # Valor límite (borde superior de longitud excedido): 281 caracteres
        "1000 " + ("a" * 276),
        # Partición inválida: fracción coloquial sin dígitos (HU-02 Escenario 2)
        "gasté media luca en dulces",
        # Partición inválida (agregada tras mutación M-04): cifra + fracción 'media'
        "gasté 1 y media lucas en dulces",
        # Partición inválida: múltiples montos en una misma oración (Ambigüedad P-03)
        "almuerzo 15 mil y gasolina 10 mil",
        # Partición inválida: cadena vacía
        "",
        # Partición inválida: cadena con solo espacios en blanco
        "    ",
    ],
)
def test_extraer_monto_particiones_y_limites_invalidos(
    texto_invalido: str,
) -> None:
    """Verifica que las particiones inválidas y bordes fuera de rango lancen error."""
    patron_exacto = r"^Monto ambiguo\. Por favor indique el valor en cifras numéricas$"
    assert MENSAJE_MONTO_AMBIGUO.startswith("Monto ambiguo")
    with pytest.raises(ValueError, match=patron_exacto):
        extraer_monto(texto_invalido)


# ==============================================================================
# REGLA 2: guardar_presupuesto(monto_mensual: int, ruta_db) -> int (HU-05)
# ==============================================================================


@pytest.mark.parametrize(
    ("tope_entrada", "tope_esperado"),
    [
        # Partición válida: presupuesto mensual estándar de estudiante
        (600000, 600000),
        # Partición válida: actualización de presupuesto según HU-05 Escenario 1
        (750000, 750000),
        # Valor límite (borde inferior válido): primer entero positivo (1 COP)
        (1, 1),
    ],
)
def test_guardar_presupuesto_particiones_y_limites_validos(
    tope_entrada: int,
    tope_esperado: int,
    tmp_path: Path,
) -> None:
    """Verifica particiones válidas y borde inferior positivo en guardar_presupuesto."""
    ruta_db = tmp_path / "test_regla2.db"
    assert guardar_presupuesto(tope_entrada, ruta_db=ruta_db) == tope_esperado


@pytest.mark.parametrize(
    "tope_invalido",
    [
        # Valor límite (borde superior inválido): último entero no positivo (0)
        0,
        # Valor límite (borde negativo inmediato): primer entero negativo (-1)
        -1,
        # Partición inválida: monto negativo de HU-05 Escenario 2 (-50000)
        -50000,
        # Partición inválida (ambigüedad tipos Python): booleano True (subclase de int)
        True,
        # Partición inválida (ambigüedad tipos Python): booleano False
        False,
    ],
)
def test_guardar_presupuesto_particiones_y_limites_invalidos(
    tope_invalido: Any,
    tmp_path: Path,
) -> None:
    """Verifica que montos <= 0 o booleanos lancen el ValueError exacto de HU-05."""
    ruta_db = tmp_path / "test_regla2_inv.db"
    with pytest.raises(ValueError, match=f"^{MENSAJE_PRESUPUESTO_INVALIDO}$"):
        guardar_presupuesto(tope_invalido, ruta_db=ruta_db)


# ==============================================================================
# REGLA 3: clasificar_gasto(texto: str) -> tuple[str, bool] (HU-03)
# ==============================================================================


@pytest.mark.parametrize(
    ("frase_gasto", "categoria_esperada", "ambiguo_esperado"),
    [
        # Partición válida: categoría Transporte/Moto (repuestos y lubricantes)
        ("cambio pastillas de freno y aceite moto 45000", "Transporte/Moto", False),
        # Partición válida: categoría Alimentación con tildes y letra 'ñ'
        ("almuerzo navideño y café en cafetería 18000", "Alimentación", False),
        # Partición válida: categoría Estudio (HU-03 Escenario 1)
        ("fotocopias taller de sistemas 4500", "Estudio", False),
        # Partición válida: categoría Ocio (vestuario y recreación)
        ("compra chaqueta y boleta cine 95000", "Ocio", False),
        # Partición válida de concepto ambiguo: cae en Gastos Varios con es_ambiguo=True
        ("pago asunto x 30000", "Gastos Varios", True),
    ],
)
def test_clasificar_gasto_particiones(
    frase_gasto: str,
    categoria_esperada: str,
    ambiguo_esperado: bool,
) -> None:
    """Verifica la clasificación temática automática y la marca de ambigüedad HU-03."""
    categoria, es_ambiguo = clasificar_gasto(frase_gasto)
    assert categoria == categoria_esperada
    assert es_ambiguo is ambiguo_esperado


def test_fixture_datos_sinteticos_locales_con_casos_dificiles(
    dataset_gastos_sinteticos_locales: dict[str, Any],
) -> None:
    """Evalúa el fixture sintético local con tildes, 'ñ', apóstrofo, vacío y cero."""
    comercio = dataset_gastos_sinteticos_locales["contexto_ficticio"]["comercio"]
    assert "Ficticia" in comercio

    for (
        frase,
        monto_esp,
        cat_esp,
        amb_esp,
        concepto_esp,
    ) in dataset_gastos_sinteticos_locales["casos_validos_dificiles"]:
        assert extraer_monto(frase) == monto_esp
        assert clasificar_gasto(frase) == (cat_esp, amb_esp)
        assert extraer_concepto(frase) == concepto_esp

    casos_inv = dataset_gastos_sinteticos_locales["casos_invalidos_dificiles"]
    for frase_invalida in casos_inv:
        with pytest.raises(ValueError, match=r"^Monto ambiguo\."):
            extraer_monto(frase_invalida)


# ==============================================================================
# REGLA 4 (MULTICONDICIÓN - TABLA DE DECISIÓN Y LÍMITES): HU-04 y HU-06
# ==============================================================================


@pytest.mark.parametrize(
    (
        "presupuesto",
        "gasto_previo",
        "frase_nuevo_gasto",
        "confirmado",
        "reg_esperado",
        "conf_esperada",
        "sobregiro_esperado",
        "pct_esperado",
    ),
    [
        # Regla R1 (Tabla decisión): C1=No (sin presupuesto configurado)
        (None, 0, "almuerzo corriente 14000", False, True, False, None, 0.0),
        # Regla R2 (Tabla decisión): C1=Sí, C2=Sí (>50%: 62.5%), C3=No (sin confirmar)
        (400000, 0, "reparación motora 250000", False, False, True, None, 62.5),
        # Regla R3 (Tabla decisión): C1=Sí, C2=No (<=50%), C4=No (saldo >= 0)
        (600000, 206000, "almuerzo corriente 14000", False, True, False, None, 2.3),
        # Regla R4 (Tabla decisión): C1=Sí, C2=No (<=50%), C4=Sí (saldo < 0: -$15.000)
        (
            400000,
            320000,
            "compra chaqueta 95000",
            False,
            True,
            False,
            MENSAJE_ALERTA_SOBREGIRO,
            23.7,
        ),
        # Regla R5 (Tabla decisión): C1=Sí, C2=Sí (>50%), C3=Sí (confirmado), C4=No
        (400000, 0, "reparación motora 250000", True, True, False, None, 62.5),
        # Regla R6 (Tabla decisión): C1=Sí, C2=Sí (>50%), C3=Sí (confirmado), C4=Sí
        (
            400000,
            200000,
            "reparación motora 250000",
            True,
            True,
            False,
            MENSAJE_ALERTA_SOBREGIRO,
            62.5,
        ),
    ],
)
def test_tabla_decision_alertas_hu06(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    presupuesto: int | None,
    gasto_previo: int,
    frase_nuevo_gasto: str,
    confirmado: bool,
    reg_esperado: bool,
    conf_esperada: bool,
    sobregiro_esperado: str | None,
    pct_esperado: float,
    tmp_path: Path,
) -> None:
    """Verifica las 6 reglas (R1 a R6) de la Tabla de Decisión de HU-04 y HU-06."""
    ruta_db = tmp_path / "test_decision.db"
    if presupuesto is not None:
        guardar_presupuesto(presupuesto, ruta_db=ruta_db)
    if gasto_previo > 0:
        insertar_transaccion(
            concepto="Gasto acumulado previo",
            monto=gasto_previo,
            categoria="Gastos Varios",
            ruta_db=ruta_db,
        )

    resultado = registrar_gasto_desde_texto(
        frase_nuevo_gasto,
        confirmado=confirmado,
        ruta_db=ruta_db,
    )

    assert resultado["registrado"] is reg_esperado
    assert resultado["requiere_confirmacion"] is conf_esperada
    assert resultado["alerta_sobregiro"] == sobregiro_esperado
    assert resultado["porcentaje_presupuesto"] == pytest.approx(pct_esperado, abs=0.05)


@pytest.mark.parametrize(
    (
        "gasto_previo",
        "frase_borde",
        "reg_esperado",
        "conf_esperada",
        "sobregiro_esperado",
        "saldo_esperado",
        "pct_gasto_esperado",
    ),
    [
        # Valor límite 50.0% exacto (200.000 de 400.000): último que NO pide confirmar
        (0, "repuesto moto 200000", True, False, None, 200000, 50.0),
        # Valor límite >50.0% por 1 peso (200.001 de 400.000): primero que SÍ pide
        (0, "repuesto moto 200001", False, True, None, 400000, 50.0),
        # Valor límite saldo exacto en 0 (gasto 80.000 de 80.000): NO hay sobregiro
        (320000, "compra chaqueta 80000", True, False, None, 0, 20.0),
        # Valor límite saldo en -1 (gasto 80.001 de 80.000): primer peso en sobregiro
        (
            320000,
            "compra chaqueta 80001",
            True,
            False,
            MENSAJE_ALERTA_SOBREGIRO,
            -1,
            20.0,
        ),
    ],
)
def test_limites_umbral_50_y_sobregiro(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    gasto_previo: int,
    frase_borde: str,
    reg_esperado: bool,
    conf_esperada: bool,
    sobregiro_esperado: str | None,
    saldo_esperado: int,
    pct_gasto_esperado: float,
    tmp_path: Path,
) -> None:
    """Verifica los pares de valores límite en los bordes de 50% y saldo 0 vs -1."""
    ruta_db = tmp_path / "test_limites_hu06.db"
    guardar_presupuesto(400000, ruta_db=ruta_db)
    if gasto_previo > 0:
        insertar_transaccion(
            concepto="Acumulado previo",
            monto=gasto_previo,
            categoria="Gastos Varios",
            ruta_db=ruta_db,
        )

    resultado = registrar_gasto_desde_texto(
        frase_borde,
        confirmado=False,
        ruta_db=ruta_db,
    )
    resumen = obtener_resumen_financiero(ruta_db=ruta_db)

    assert resultado["registrado"] is reg_esperado
    assert resultado["requiere_confirmacion"] is conf_esperada
    assert resultado["alerta_sobregiro"] == sobregiro_esperado
    assert resultado["porcentaje_presupuesto"] == pytest.approx(
        pct_gasto_esperado, abs=0.1
    )
    assert resumen["saldo_disponible"] == saldo_esperado

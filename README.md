# Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)

Aplicación en Python 3.10+ diseñada bajo principios de **Arquitectura Limpia** y **Desarrollo Guiado por Pruebas (TDD)** para registrar, normalizar y analizar gastos personales expresados en lenguaje natural y jerga cotidiana colombiana.

---

## Funcionalidad de la semana 5

### Historia de Usuario: `HU-02` — Normalización de expresiones coloquiales y jerga monetaria
- **Prioridad:** Must
- **Descripción:** Como usuario de la aplicación de finanzas personales, quiero poder registrar mis gastos utilizando expresiones coloquiales colombianas (como *"lucas"* o *"mil"*) o cifras con formato numérico tradicional, para que el sistema convierta automáticamente el valor a un monto numérico entero estandarizado sin obligarme a digitar todos los ceros manualmente.

#### Criterios de Aceptación (Gherkin)
- **Escenario 1: Conversión exitosa de jerga monetaria y formatos numéricos a entero**
  - **Dado** que el usuario ingresa una descripción de gasto con una cifra numérica acompañada de términos coloquiales como `"lucas"`, `"luca"`, `"mil"`, o una cifra con punto separador de miles (ej. `"20 lucas en almuerzo"`, `"12 mil en bus"`, `"4.500"`),
  - **Cuando** el sistema procesa el texto mediante el módulo de normalización de montos,
  - **Entonces** extrae y retorna el valor equivalente como un número entero positivo en pesos colombianos (`20000`, `12000`, `4500`).

- **Escenario 2: Rechazo de montos ambiguos o sin cifras numéricas**
  - **Dado** que el usuario ingresa una expresión monetaria ambigua, fraccionaria en texto o sin dígitos numéricos (ej. `"gasté media luca en dulces"`),
  - **Cuando** el sistema intenta extraer el monto del texto,
  - **Entonces** rechaza la entrada lanzando una excepción `ValueError` con el mensaje exacto: `"Monto ambiguo. Por favor indique el valor en cifras numéricas"`.

---

### Contrato de la Función `extraer_monto`

- **Ubicación:** `src/parser_montos.py`
- **Firma con tipos:**
  ```python
  def extraer_monto(texto: str) -> int:
  ```
- **Entradas (Parámetros):**
  - `texto` (`str`): Cadena de texto en lenguaje natural que describe un gasto o contiene un valor monetario (ej. `"20 lucas en comida"`, `"12 mil"`, `"14000"`, `"4.500"`).
- **Salidas (Retorno):**
  - `int`: Monto monetario normalizado como un número entero positivo (`> 0`) en pesos colombianos (COP).
- **Supuestos:**
  - La unidad monetaria de referencia es el peso colombiano (COP), sin centavos.
  - Los términos coloquiales `"luca"`, `"lucas"` y `"mil"` actúan como multiplicadores por `1000` sobre la cifra numérica que los precede.
  - El punto (`.`) seguido de bloques de exactamente tres dígitos (ej. `"4.500"` o `"12.000"`) se interpreta como separador de miles y no como punto decimal.
- **Casos límite:**
  - **Insensibilidad a mayúsculas/minúsculas:** Reconoce variantes como `"1 LUCA"`, `"20 Lucas"`, `"15 MIL"`.
  - **Separadores de miles con punto:** Convierte `"4.500"` en `4500` antes de operar.
  - **Espacios adicionales:** Tolera espacios al inicio, al final o múltiples espacios entre el número y el multiplicador coloquial.
  - **Cifras planas:** Si el número no va seguido de `"luca(s)"` ni `"mil"` (ej. `"14000"`), retorna el entero directamente (`14000`).
- **Excepciones:**
  - `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")`: Se lanza cuando:
    - El texto no contiene ninguna cifra numérica (ej. `"gasté media luca en dulces"`, `"compre algo caro"`).
    - El texto contiene cuantificadores ambiguos o fracciones textuales antes del multiplicador (ej. `"media luca"`).
    - El texto está vacío (`""` o solo espacios) o el valor numérico resultante es menor o igual a cero (`0`).
    - Hay múltiples montos contradictorios o un formato numérico malformado que impide determinar un único valor con certeza.

#### Ejemplos de Entrada y Salida

| # | Entrada (`texto`) | Salida Esperada / Comportamiento | Explicación |
|---|---|---|---|
| 1 | `"20 lucas en almuerzo"` | `20000` | Multiplica `20` por `1000` al detectar `"lucas"`. |
| 2 | `"pagué 12 mil en transporte"` | `12000` | Multiplica `12` por `1000` al detectar `"mil"`. |
| 3 | `"1 LUCA"` | `1000` | Caso límite en mayúsculas y singular (`"LUCA"`). |
| 4 | `"café 4.500"` | `4500` | Caso límite con punto separador de miles. |
| 5 | `"14000"` | `14000` | Cifra numérica directa sin jerga. |
| 6 | `"gasté media luca en dulces"` | `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")` | Rechaza expresiones sin cifra numérica clara (Escenario 2 de `HU-02`). |

---

## Ejecución de Pruebas y Calidad de Código

1. **Activar el entorno virtual e instalar dependencias:**
   ```powershell
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Ejecutar la suite de pruebas automatizadas:**
   ```powershell
   pytest -v
   ```

3. **Verificar calidad de código (PEP 8 / RNF-05 >= 9.0/10):**
   ```powershell
   pylint src/ tests/
   ```

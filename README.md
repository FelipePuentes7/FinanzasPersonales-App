# Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)

---

## 1. Qué es

**FinanzasPersonales-App** es una aplicación en Python 3.10+ diseñada bajo principios de **Arquitectura Limpia**, **Desarrollo Guiado por Pruebas (TDD)** y **Desarrollo Seguro (AppSec)** para registrar, normalizar y analizar gastos personales expresados en lenguaje natural y jerga cotidiana colombiana.

En este primer incremento funcional revisado (Semanas 5 y 6), el proyecto implementa y asegura el módulo de dominio correspondiente a la historia de usuario prioritaria **`HU-02: Normalización de expresiones coloquiales y jerga monetaria`**, encargado de transformar descripciones de gastos en texto libre (como `"20 lucas en almuerzo"`, `"12 mil en bus"` o `"4.500"`) en montos enteros estandarizados en pesos colombianos (COP), rechazando entradas ambiguas, montos negativos o cargas maliciosas (DoS).

---

## 2. Requisitos

- **Lenguaje:** Python `3.10` o superior (probado en Python `3.12.10`).
- **Gestor de paquetes:** `pip` y módulo estándar `venv`.
- **Control de versiones:** `Git`.
- **Dependencias del proyecto (versiones exactas fijadas en [`requirements.txt`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/requirements.txt)):**
  - `pytest==9.2.0` (ejecución de pruebas unitarias y de abuso).
  - `ruff==0.11.2` (linter estático de estilo, errores, bugs probables y seguridad `E, F, B, S`).
  - `pylint==4.1.4` (verificación de calidad y mantenibilidad PEP 8 >= 9.0/10).
  - `pip-audit==2.9.0` (auditoría de vulnerabilidades conocidas en dependencias).

---

## 3. Instalación

Ejecute los siguientes comandos en una terminal desde una carpeta limpia para clonar el repositorio, configurar el entorno virtual e instalar las dependencias:

```powershell
# 1. Clonar el repositorio e ingresar al directorio del proyecto
git clone https://github.com/FelipePuentes7/FinanzasPersonales-App.git
cd FinanzasPersonales-App

# 2. Crear y activar el entorno virtual
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar las dependencias con versiones fijadas
pip install -r requirements.txt

# 4. Crear el archivo local de variables de entorno a partir de la plantilla
Copy-Item .env.example .env
```

*(En Linux/macOS, active el entorno con `source venv/bin/activate` y copie la plantilla con `cp .env.example .env`).*

---

## 4. Ejecución

Para probar directamente el módulo de normalización de montos (`src/parser_montos.py`) desde la línea de comandos con el entorno virtual activo, ejecute:

```powershell
python -c "from src.parser_montos import extraer_monto; print('20 lucas ->', extraer_monto('gasté 20 lucas en almuerzo')); print('4.500 ->', extraer_monto('café 4.500'))"
```

**Salida esperada:**
```text
20 lucas -> 20000
4.500 -> 4500
```

---

## 5. Pruebas

El proyecto cuenta con una suite automatizada de **7 pruebas** (5 pruebas funcionales y casos límite de TDD de la Semana 5 + 2 pruebas de abuso de seguridad de la Semana 6) y herramientas de análisis estático configuradas en [`pyproject.toml`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/pyproject.toml):

```powershell
# 1. Ejecutar todas las pruebas unitarias y de abuso
pytest -v

# 2. Ejecutar el linter ruff con reglas de estilo, errores, bugs y seguridad (E, F, B, S)
ruff check --select E,F,B,S .

# 3. Verificar puntuación de calidad PEP 8 (RNF-05 >= 9.0/10)
pylint src/ tests/

# 4. Auditar vulnerabilidades en las dependencias instaladas
pip-audit -r requirements.txt
```

---

## 6. Estructura

```text
FinanzasPersonales-App/
├── src/
│   ├── __init__.py              # Inicializador del paquete de código fuente
│   └── parser_montos.py         # Módulo de dominio HU-02: extraer_monto y validaciones de seguridad
├── tests/
│   ├── __init__.py              # Inicializador del paquete de pruebas
│   └── test_parser_montos.py    # Suite de 7 pruebas unitarias y de abuso con pytest
├── .env.example                 # Plantilla de variables de entorno (sin secretos reales)
├── .gitignore                   # Exclusión de .env, venv/, cachés y bases de datos *.db
├── bitacora_ia.md               # Registro auditable de prompts, decisiones y supervisión de IA
├── pyproject.toml               # Configuración central del proyecto, pytest y ruff (E, F, B, S)
├── requirements.txt             # Dependencias con versiones exactas fijadas (==)
├── revision_seguridad.md        # Informe de revisión de código, seguridad y verificación de IA
└── README.md                    # Documentación general y contrato funcional del proyecto
```

---

## 7. Uso de IA

El desarrollo de este repositorio utilizó **Google Antigravity (Modo Agente y Chat)** bajo supervisión humana estricta siguiendo estas prácticas de ingeniería:

- **TDD estricto e inmutabilidad de pruebas:** Las pruebas unitarias iniciales se escribieron antes de la implementación (Fase Roja) y no se modificaron para hacer pasar el código.
- **Segunda revisión de seguridad verificada:** Cada hallazgo reportado por el linter y la IA fue verificado manualmente en el código fuente, separando problemas reales (`H-01`, `H-02`, `H-03`) de falsos positivos (`FP-01`, `FP-02`, `FP-03`) en [`revision_seguridad.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/revision_seguridad.md).
- **Supervisión de agente en rama dedicada:** Las correcciones de seguridad y nuevas pruebas de abuso se aplicaron en la rama `fix/semana-6-seguridad`, revisando el `git diff` antes de su integración a `main`.
- **Trazabilidad completa:** Todas las sugerencias aceptadas, ajustadas y rechazadas se encuentran documentadas en [`bitacora_ia.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/bitacora_ia.md).

---

## 8. Autor y licencia

- **Autor:** Andrés Felipe Puentes
- **Contexto:** Proyecto de Ingeniería de Software — Aplicación de Finanzas Personales con IA (2026).
- **Licencia:** Distribuido bajo la licencia **MIT**.

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
  - **Dado** que el usuario ingresa una expresión monetaria ambigua, fraccionaria en texto, negativa, sobredimensionada o sin dígitos numéricos (ej. `"gasté media luca en dulces"`, `"gasté -20 lucas"`),
  - **Cuando** el sistema intenta extraer el monto del texto,
  - **Entonces** rechaza la entrada lanzando una excepción `ValueError` con el mensaje exacto: `"Monto ambiguo. Por favor indique el valor en cifras numéricas"`.

### Contrato de la Función `extraer_monto`

- **Ubicación:** `src/parser_montos.py`
- **Firma con tipos:**
  ```python
  def extraer_monto(texto: str) -> int:
  ```
- **Entradas (Parámetros):**
  - `texto` (`str`): Cadena de texto en lenguaje natural que describe un gasto o contiene un valor monetario (longitud máxima permitida: `280` caracteres).
- **Salidas (Retorno):**
  - `int`: Monto monetario normalizado como un número entero positivo (`> 0`) en pesos colombianos (COP).
- **Supuestos:**
  - La unidad monetaria de referencia es el peso colombiano (COP), sin centavos.
  - Los términos coloquiales `"luca"`, `"lucas"` y `"mil"` actúan como multiplicadores por `1000` sobre la cifra numérica que los precede.
  - El punto (`.`) seguido de bloques de exactamente tres dígitos (ej. `"4.500"` o `"12.000"`) se interpreta como separador de miles y no como punto decimal.
- **Casos límite y de abuso:**
  - **Insensibilidad a mayúsculas/minúsculas:** Reconoce variantes como `"1 LUCA"`, `"20 Lucas"`, `"15 MIL"`.
  - **Separadores de miles con punto:** Convierte `"4.500"` en `4500` antes de operar.
  - **Cifras planas:** Si el número no va seguido de `"luca(s)"` ni `"mil"` (ej. `"14000"`), retorna el entero directamente (`14000`).
  - **Mitigación de abuso (`H-01` y `H-02`):** Rechaza montos precedidos por signo negativo (`"-20 lucas"`) y entradas que superen `LONGITUD_MAXIMA_TEXTO` (`280` caracteres).
- **Excepciones:**
  - `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")`: Se lanza cuando el texto está vacío, supera los 280 caracteres, contiene montos negativos o cero, incluye cuantificadores fraccionarios sin cifras (`"media luca"`), no contiene dígitos o presenta múltiples montos contradictorios.

#### Ejemplos de Entrada y Salida

| # | Entrada (`texto`) | Salida Esperada / Comportamiento | Explicación |
|---|---|---|---|
| 1 | `"20 lucas en almuerzo"` | `20000` | Multiplica `20` por `1000` al detectar `"lucas"`. |
| 2 | `"pagué 12 mil en transporte"` | `12000` | Multiplica `12` por `1000` al detectar `"mil"`. |
| 3 | `"1 LUCA"` | `1000` | Caso límite en mayúsculas y singular (`"LUCA"`). |
| 4 | `"café 4.500"` | `4500` | Caso límite con punto separador de miles. |
| 5 | `"14000"` | `14000` | Cifra numérica directa sin jerga. |
| 6 | `"gasté media luca en dulces"` | `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")` | Rechaza expresiones sin cifra numérica clara (Escenario 2 de `HU-02`). |
| 7 | `"gasté -20 lucas en almuerzo"` | `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")` | Caso de abuso (`H-01`): rechaza montos negativos. |

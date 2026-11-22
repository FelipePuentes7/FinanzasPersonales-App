# Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)

---

## 1. Qué es

**FinanzasPersonales-App** es una aplicación web local en Python 3.10+ diseñada bajo principios de **Arquitectura Limpia**, **Desarrollo Guiado por Pruebas (TDD)** y **Desarrollo Seguro (AppSec)** para ayudar a estudiantes universitarios a registrar, clasificar y controlar sus gastos diarios expresados en lenguaje natural y jerga cotidiana colombiana.

El sistema integra la totalidad del alcance funcional y no funcional definido en la especificación de requisitos:
- **`HU-01` y `HU-02` (Prioridad Must):** Captura de gastos en un único campo de texto con `autofocus` (`RNF-04`: máximo 2 interacciones) y normalización de modismos colombianos (`lucas`, `luca`, `mil`) y puntos de miles.
- **`HU-03` (Prioridad Must):** Clasificación temática automática en 5 categorías fijas (`Transporte/Moto`, `Alimentación`, `Estudio`, `Ocio`, `Gastos Varios`) con anonimización de datos personales (`RNF-03`), fallback offline determinista (`RNF-02`) y reclasificación con un clic para conceptos ambiguos.
- **`HU-04` y `HU-05` (Prioridad Must / Should):** Panel visual con tarjetas de Presupuesto Mensual, Total Gastado, Saldo Restante Disponible (verde o rojo según estado), barra de progreso porcentual y panel lateral de configuración de presupuesto.
- **`HU-06` (Prioridad Should):** Alertas preventivas de sobregiro (`[ALERTA DE SOBREGIRO]`) y modal de confirmación cuando un gasto individual supera el 50% del presupuesto mensual.
- **`HU-07` y `HU-08` (Prioridad Could):** Filtrado instantáneo por categoría en modo offline con cálculo de subtotal y exportación a archivo plano estándar `gastos_<mes>_<anio>.csv`.

---

## 2. Requisitos

- **Lenguaje:** Python `3.10` o superior (verificado en Python `3.12.10`).
- **Gestor de paquetes y entorno:** `pip` y módulo estándar `venv`.
- **Base de datos:** `sqlite3` (incluido en la biblioteca estándar de Python, persistencia local en `data/finanzas.db`).
- **Dependencias con versiones exactas fijadas en [`requirements.txt`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/requirements.txt):**
  - `pytest==9.2.0` (suite de 27 pruebas unitarias, de abuso y de integración web).
  - `ruff==0.11.2` (linter estático con reglas `E, F, B, S`).
  - `pylint==4.1.4` (análisis estático PEP 8 con calificación `10.00/10` >= 9.0 exigido por `RNF-05`).
  - `pip-audit==2.9.0` (auditoría de vulnerabilidades en dependencias).

---

## 3. Instalación

Ejecute los siguientes comandos desde una terminal en una carpeta limpia:

```powershell
# 1. Clonar el repositorio y entrar a la carpeta del proyecto
git clone https://github.com/FelipePuentes7/FinanzasPersonales-App.git
cd FinanzasPersonales-App

# 2. Crear y activar el entorno virtual
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar las dependencias fijadas
pip install -r requirements.txt

# 4. Crear el archivo local de variables de entorno a partir de la plantilla
Copy-Item .env.example .env
```

*(En Linux/macOS active el entorno con `source venv/bin/activate` y copie la plantilla con `cp .env.example .env`).*

---

## 4. Ejecución

### A. Iniciar el Panel Web Interactivo (`http://127.0.0.1:5000`)

```powershell
python app.py
```

Abra su navegador en **`http://127.0.0.1:5000`** para usar el panel visual, configurar su presupuesto mensual en la barra lateral, registrar gastos en lenguaje natural, filtrar por categoría y exportar el reporte CSV.

### B. Probar los Módulos de Dominio por Consola

```powershell
python -c "from src.parser_montos import extraer_monto; from src.clasificador import clasificar_gasto; print('Monto:', extraer_monto('20 lucas de gasolina para la moto'), '| Categoría:', clasificar_gasto('20 lucas de gasolina para la moto')[0])"
```

---

## 5. Pruebas

Ejecute la suite completa de **27 pruebas automatizadas** y las herramientas de calidad y seguridad con los siguientes comandos:

```powershell
# 1. Ejecutar todas las pruebas unitarias, de abuso y de integración web
pytest -v

# 2. Ejecutar el linter ruff con reglas de estilo, errores, bugs y seguridad (E, F, B, S)
ruff check --select E,F,B,S .

# 3. Verificar calificación PEP 8 en pylint (RNF-05 >= 9.0/10)
pylint app.py src/ tests/

# 4. Auditar vulnerabilidades conocidas en dependencias
pip-audit -r requirements.txt
```

---

## 6. Estructura

```text
FinanzasPersonales-App/
├── app.py                       # Servidor web local WSGI, rutas HTTP y cliente de pruebas
├── src/
│   ├── __init__.py              # Inicializador del paquete de dominio
│   ├── parser_montos.py         # HU-02: Extracción de montos y mitigación de abuso (H-01, H-02)
│   ├── database.py              # HU-04, HU-05, HU-07: Persistencia SQLite 100% parametrizada (?)
│   ├── clasificador.py          # HU-01, HU-03, RNF-02, RNF-03: Clasificador híbrido/offline y privacidad
│   └── servicios.py             # HU-04, HU-06, HU-08: Orquestación, alertas >50%/sobregiro y CSV
├── templates/
│   └── index.html               # Interfaz web HTML5 con tarjetas métricas, barra y tabla filtrable
├── static/
│   └── style.css                # Hoja de estilos moderna y responsiva (estados verde/rojo/ámbar)
├── tests/
│   ├── __init__.py              # Inicializador del paquete de pruebas
│   ├── test_parser_montos.py    # 7 pruebas de HU-02 (5 originales TDD + 2 pruebas de abuso)
│   ├── test_database.py         # 6 pruebas de SQLite parametrizado e inyección SQL
│   ├── test_clasificador.py     # 5 pruebas de clasificación, fallback offline y privacidad RNF-03
│   ├── test_servicios.py        # 5 pruebas de métricas, alertas HU-06 y exportación CSV HU-08
│   └── test_app.py              # 4 pruebas de integración de rutas web y rendimiento RNF-01
├── .env.example                 # Plantilla de variables de entorno sin secretos reales
├── .gitignore                   # Exclusión de .env, data/, *.db, venv/ y cachés
├── bitacora_ia.md               # Bitácora auditable de decisiones de IA (Semanas 5, 6 y MVP)
├── pyproject.toml               # Configuración de pytest y ruff (reglas E, F, B, S)
├── requirements.txt             # Dependencias con versiones exactas fijadas (==)
├── revision_seguridad.md        # Informe de auditoría AppSec, hallazgos y verificación de IA
└── README.md                    # Documentación general y contratos del proyecto
```

---

## 7. Uso de IA

El desarrollo del proyecto empleó **Google Antigravity (Modo Agente y Chat)** bajo supervisión técnica rigurosa:
- **Desarrollo Guiado por Pruebas (TDD):** Las pruebas de `HU-02` se escribieron antes de la implementación y se mantuvieron inalteradas durante todo el proyecto.
- **Seguridad desde el Diseño (AppSec):** Todas las consultas SQL en [`src/database.py`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/src/database.py) usan parámetros `?`; todas las salidas HTML en [`app.py`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/app.py) aplican `html.escape` contra XSS; y [`src/clasificador.py`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/src/clasificador.py) anonimiza cédulas, nombres y direcciones antes de armar cualquier payload LLM (`RNF-03`).
- **Trazabilidad y Auditoría:** Cada hito de código, revisión de seguridad y trabajo en ramas (`fix/semana-6-seguridad` y `feat/mvp-web-sqlite`) está registrado en [`bitacora_ia.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/bitacora_ia.md) y [`revision_seguridad.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/revision_seguridad.md).

---

## 8. Autor y licencia

- **Autor:** Andrés Felipe Puentes Rivera
- **Contexto:** Proyecto Final — Seminario Inteligencia Artificial Aplicada al Ciclo de Vida del Software (2026).
- **Licencia:** Distribuido bajo la licencia **MIT**.

---

## Funcionalidad de la semana 5

### Historia de Usuario: `HU-02` — Normalización de expresiones coloquiales y jerga monetaria
- **Prioridad:** Must
- **Descripción:** Como estudiante universitario, quiero que el sistema reconozca términos como `'lucas'` o `'mil'` para evitar digitar manualmente todos los ceros de una cantidad.
- **Contrato:** `extraer_monto(texto: str) -> int` en [`src/parser_montos.py`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/src/parser_montos.py). Recibe una frase en lenguaje natural (`<= 280` caracteres) y retorna el monto entero positivo en COP, o lanza `ValueError("Monto ambiguo. Por favor indique el valor en cifras numéricas")` ante expresiones sin cifras claras, negativas o ambiguas.
- **Comando de pruebas:** `pytest -v`

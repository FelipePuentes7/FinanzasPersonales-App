# Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)

---

## 1. Qué es

**FinanzasPersonales-App** es una aplicación web local en Python 3.10+ diseñada bajo principios de **Arquitectura Limpia**, **Desarrollo Guiado por Pruebas (TDD)** y **Desarrollo Seguro (AppSec)** para ayudar a estudiantes universitarios a registrar, clasificar y controlar sus gastos diarios expresados en lenguaje natural y jerga cotidiana colombiana.

El sistema integra la totalidad del alcance funcional y no funcional definido en la especificación de requisitos, más la evolución de producto (Iteración 2 del SDLC) para control financiero real:
- **`HU-01` y `HU-02` (Prioridad Must):** Captura de gastos en un único campo de texto con `autofocus` (`RNF-04`: máximo 2 interacciones) y normalización de modismos colombianos (`lucas`, `luca`, `mil`) y puntos de miles.
- **`HU-03` (Prioridad Must):** Clasificación temática automática en 5 categorías fijas (`Transporte/Moto`, `Alimentación`, `Estudio`, `Ocio`, `Gastos Varios`) con anonimización de datos personales (`RNF-03`), fallback offline determinista (`RNF-02`) y reclasificación con un clic para conceptos ambiguos.
- **`HU-04` y `HU-05` (Prioridad Must / Should):** Panel visual con tarjetas de Presupuesto Mensual, Ingresos Extra, Total Gastado, Saldo Restante Disponible (verde o rojo según estado), barra de progreso porcentual y panel de configuración de presupuesto.
- **`HU-06` (Prioridad Should):** Alertas preventivas de sobregiro (`[ALERTA DE SOBREGIRO]`) y modal de confirmación cuando un gasto individual supera el 50% del presupuesto mensual.
- **`HU-07` y `HU-08` (Prioridad Could):** Filtrado instantáneo por categoría en modo offline con cálculo de subtotal y exportación a archivo plano estándar `gastos_<mes>_<anio>.csv`.
- **`HU-09` (Evolución SDLC - Ingresos Extra y Recuperación de Saldo):** Registro ágil de ingresos adicionales o abonos en lenguaje natural (ej. `"me entraron 1.200.000 de trabajo extra"`, `"ingreso 500 lucas"`) o mediante selector de 1 clic, recalculando el saldo disponible (`Presupuesto Base + Ingresos Extra - Total Gastado`) para mitigar o salir de estados de sobregiro.
- **`HU-10` (Evolución SDLC - Gastos Fijos Mensuales):** Plantilla persistente de compromisos mensuales recurrentes (arriendo, internet, plan celular, servicios) con aplicación al balance del mes en 1 clic sin redigitarlos desde cero.
- **`HU-11` (Evolución SDLC - Control de Créditos y Cuotas):** Seguimiento de obligaciones a plazos (nombre del crédito, valor de cuota, progreso `cuotas_pagadas / total_cuotas`, saldo pendiente) con botón rápido `"Registrar pago de cuota"` que descuenta del disponible mensual y avanza el contador de cuotas.
- **`HU-12` (Evolución Producto - Sistema Multiusuario y Autenticación con `scrypt`):** Registro (`/register`) e inicio de sesión (`/login`) con contraseñas protegidas mediante `scrypt` + sal criptográfica aleatoria y aislamiento estricto de datos por `usuario_id` en SQLite.
- **`HU-13` (Evolución Producto - Contabilidad Mes a Mes con Arrastre Inteligente / Rollover):** Navegación por periodos mensuales (`YYYY-MM`) y cierre mensual que arrastra automáticamente el saldo a favor (ahorro/ganancia) o el saldo pendiente (deuda/sobregiro) hacia el mes siguiente, junto con cálculo de **Meta de Ahorro** y **Presupuesto Diario Sugerido**.
- **`HU-14` (Evolución Producto - Analítica Visual Minimalista y Buscador Instantáneo):** Interfaz de producto fintech limpia (sin códigos académicos internos en la vista del usuario), equipada con gráficas interactivas en Chart.js (dona de distribución por categoría y barras de flujo mensual) y buscador en tiempo real.

---

## 2. Requisitos

- **Lenguaje:** Python `3.10` o superior (verificado en Python `3.12.10`).
- **Gestor de paquetes y entorno:** `pip` y módulo estándar `venv`.
- **Base de datos:** `sqlite3` (incluido en la biblioteca estándar de Python, persistencia local en `data/finanzas.db`).
- **Dependencias con versiones exactas fijadas en [`requirements.txt`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/requirements.txt):**
  - `pytest==9.2.0` (suite de 81 pruebas unitarias, parametrizadas, de abuso, aislamiento multiusuario y rollover mensual).
  - `ruff==0.11.2` (linter estático con reglas `E, F, B, S`).
  - `pylint==4.1.4` (análisis estático PEP 8 con calificación `>= 9.9/10` superando el mínimo de 9.0 exigido por `RNF-05`).
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

Ejecute la suite completa de **81 pruebas automatizadas** y las herramientas de calidad y seguridad con los siguientes comandos:

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
├── app.py                               # Servidor web local WSGI, sesiones HttpOnly y rutas HTTP
├── src/
│   ├── __init__.py                      # Inicializador del paquete de dominio
│   ├── auth.py                          # HU-12: Autenticación y hash de contraseñas con scrypt + sal
│   ├── parser_montos.py                 # HU-02: Extracción de montos y mitigación de abuso (H-01, H-02)
│   ├── database.py                      # Esquema SQLite de 6 tablas 100% parametrizadas (?) por usuario_id
│   ├── clasificador.py                  # HU-01, HU-03, RNF-02, RNF-03: Clasificador híbrido/offline y privacidad
│   └── servicios.py                     # HU-04 a HU-14: Rollover mensual, presupuesto diario, alertas y CSV
├── templates/
│   ├── index.html                       # Dashboard comercial Bolsillo con Chart.js, buscador y selector de mes
│   ├── login.html                       # Pantalla minimalista de inicio de sesión con logo SVG
│   └── register.html                    # Pantalla minimalista de creación de cuenta
├── static/
│   └── style.css                        # Hoja de estilos minimalista fintech (paleta índigo/esmeralda/coral)
├── tests/
│   ├── __init__.py                      # Inicializador del paquete de pruebas
│   ├── test_parser_montos.py            # 7 pruebas de HU-02 (5 originales TDD + 2 pruebas de abuso)
│   ├── test_database.py                 # 6 pruebas de SQLite parametrizado e inyección SQL
│   ├── test_clasificador.py             # 5 pruebas de clasificación, fallback offline y privacidad RNF-03
│   ├── test_servicios.py                # 5 pruebas de métricas, alertas HU-06 y exportación CSV HU-08
│   ├── test_app.py                      # 6 pruebas de integración de rutas web, login, rollover y UI limpia
│   ├── test_reglas_negocio_s7.py        # 40 pruebas formales (particiones, límites, tabla decisión y fixture)
│   ├── test_evolucion_sdlc.py           # 6 pruebas de ingresos extra, gastos fijos y créditos a cuotas
│   └── test_multiusuario_y_rollover.py  # 6 pruebas de scrypt, aislamiento multiusuario y rollover mensual
├── .env.example                         # Plantilla de variables de entorno sin secretos reales
├── .gitignore                           # Exclusión de .env, data/, *.db, venv/ y cachés
├── bitacora_ia.md                       # Bitácora auditable de decisiones de IA (24 entradas del ciclo completo)
├── pyproject.toml                       # Configuración de pytest y ruff (reglas E, F, B, S)
├── registro_pruebas.md                  # Registro formal de 6 reglas, tablas de decisión, mutación y datos
├── requirements.txt                     # Dependencias con versiones exactas fijadas (==)
├── revision_seguridad.md                # Informe de auditoría AppSec, scrypt, control de acceso y hallazgos
└── README.md                            # Documentación general y contratos del proyecto
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

---

## Evolución Funcional y de Experiencia de Usuario (SDLC — Iteración 2)

### Nuevas Historias de Usuario y Criterios de Aceptación

#### `HU-09` — Registro de ingresos extra y recuperación de saldo negativo
- **Como** usuario que maneja un presupuesto base pero recibe pagos adicionales en el mes, **quiero** registrar ingresos extra o abonos en lenguaje natural o con un selector rápido, **para** incrementar mi liquidez mensual y recuperar mi saldo disponible cuando haya caído en negativo (sobregiro).
- **Escenario 1 (Recuperación de sobregiro mediante ingreso extra):**
  - **Dado** que el presupuesto base es de `$2.000.000` y los gastos acumulados suman `$3.000.000` (saldo en sobregiro de `-$1.000.000`),
  - **Cuando** el usuario registra el ingreso `"me entraron 1.200.000 de trabajo extra"` (o selecciona tipo `Ingreso Extra`),
  - **Entonces** el sistema guarda el abono por `$1.200.000`, actualiza el saldo disponible a `+$200.000 disponible` (`$2.000.000 + $1.200.000 - $3.000.000`) y desactiva la alerta roja de sobregiro.
- **Escenario 2 (Error por ingreso inválido o sin cifra):**
  - **Dado** que el usuario intenta registrar un ingreso extra sin monto numérico válido o con valor `<= 0`,
  - **Cuando** envía el formulario,
  - **Entonces** el sistema rechaza el registro lanzando `ValueError` sin alterar el saldo disponible.

#### `HU-10` — Gestión y aplicación de gastos fijos mensuales
- **Como** usuario con obligaciones recurrentes cada mes (arriendo, internet, celular, servicios), **quiero** guardar una lista de mis gastos fijos mensuales y aplicarlos con un solo clic, **para** no tener que escribirlos manualmente uno por uno cada mes.
- **Escenario 1 (Creación y aplicación de gasto fijo al balance):**
  - **Dado** que el usuario tiene configurado el gasto fijo `"Arriendo"` por `$650.000` en la categoría `"Gastos Varios"`,
  - **Cuando** presiona `"Aplicar al mes"`,
  - **Entonces** el sistema registra automáticamente la transacción `"Gasto fijo: Arriendo"` por `$650.000` en SQLite y descuenta dicho valor del saldo disponible.
- **Escenario 2 (Error por monto de gasto fijo no positivo):**
  - **Dado** que el usuario intenta crear un gasto fijo con nombre vacío o monto `<= 0`,
  - **Cuando** envía el registro,
  - **Entonces** el sistema rechaza la operación con `ValueError("El monto del gasto fijo debe ser un entero positivo mayor a cero")`.

#### `HU-11` — Control de créditos y pago de cuotas mensuales
- **Como** usuario que paga obligaciones o compras diferidas a plazos, **quiero** llevar el control de mis créditos (valor de cuota, cuotas pagadas vs. total de cuotas) y registrar el pago de cada cuota con un clic, **para** saber cuántas cuotas me faltan y reflejar el pago inmediatamente en mi balance mensual.
- **Escenario 1 (Pago de cuota mensual y avance de progreso):**
  - **Dado** un crédito activo `"Cuota Moto"` con cuota mensual de `$320.000`, `12` cuotas totales y `3` cuotas pagadas,
  - **Cuando** el usuario pulsa `"Registrar pago de cuota"`,
  - **Entonces** el contador avanza a `4 / 12` cuotas pagadas (`8` restantes), y se inserta en el historial de gastos la transacción `"Cuota 4/12: Cuota Moto"` por `$320.000`.
- **Escenario 2 (Bloqueo de pago cuando el crédito ya está saldado):**
  - **Dado** un crédito cuyas cuotas pagadas ya alcanzaron el total de cuotas (`12 / 12`),
  - **Cuando** se intenta registrar una nueva cuota,
  - **Entonces** el sistema bloquea la operación lanzando `ValueError("Este crédito ya tiene todas sus cuotas pagadas")` sin generar cobros duplicados.

### Diseño del Esquema SQLite Evolucionado (`src/database.py`)
1. `usuarios (id, nombre, email, password_hash, creado_en)`: Cuentas de usuario con hash `scrypt` y sal criptográfica (`HU-12`).
2. `presupuesto (id, monto_mensual, actualizado_en)` y `periodos_mensuales (id, usuario_id, periodo, presupuesto_base, meta_ahorro, saldo_arrastrado, cerrado)`: Configuración presupuestal por usuario y periodo `YYYY-MM` con soporte de rollover mensual (`HU-05`, `HU-13`).
3. `transacciones (id, usuario_id, periodo, fecha, concepto, monto, categoria, es_ambiguo)`: Historial de gastos aislados por usuario y mes (`HU-01`, `HU-12`, `HU-13`).
4. `ingresos_extra (id, usuario_id, periodo, fecha, concepto, monto)`: Abonos e ingresos adicionales por usuario y periodo (`HU-09`).
5. `gastos_fijos (id, usuario_id, nombre, monto, categoria, activo)`: Plantilla de compromisos recurrentes por usuario aplicables en 1 clic (`HU-10`).
6. `creditos (id, usuario_id, nombre, valor_cuota, total_cuotas, cuotas_pagadas, categoria)`: Obligaciones diferidas a cuotas por usuario con control de avance (`HU-11`).

### Regla de Contabilidad Mensual y Arrastre (`HU-13`)
Para cada usuario y periodo mensual $t$ (`YYYY-MM`):
$$\text{Capacidad Total}_t = \text{Presupuesto Base}_t + \text{Ingresos Extra}_t + \text{Saldo Arrastrado}_{t-1}$$
$$\text{Saldo Disponible}_t = \text{Capacidad Total}_t - \text{Meta de Ahorro}_t - \text{Total Gastado}_t$$
- **Arrastre de ganancia ($\text{Saldo}_t > 0$):** Al avanzar al mes $t+1$, se suma automáticamente como *"Saldo a favor del mes anterior"*.
- **Arrastre de deuda ($\text{Saldo}_t < 0$):** Al avanzar al mes $t+1$, se descuenta automáticamente como *"Saldo pendiente del mes anterior"*.



# Bitácora de uso de IA

Proyecto: Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)
Estudiante: Andrés Felipe Puentes
Funcionalidad: HU-02 Normalización de expresiones coloquiales y jerga monetaria
Asistente usado: Google Antigravity (Modo Agente y Chat)

## Entradas

### Entrada 1

- **Fecha:** 2026-11-07
- **Prompt o sugerencia:** Definir en `README.md` el contrato formal de `extraer_monto(texto: str) -> int` y crear en `tests/test_parser_montos.py` las 5 pruebas unitarias en rojo (2 casos normales, 2 casos límite y 1 caso de error por monto ambiguo) dejando `src/parser_montos.py` únicamente con `raise NotImplementedError`.
- **Decisión:** Aceptada
- **Por qué:** Cumple estrictamente el ciclo TDD exigido en la Semana 5 (escribir el contrato y las pruebas antes que la implementación) y asegura desde el primer commit que `tests/test_parser_montos.py` cumpla el estándar PEP 8 para no tener que modificarlo en fases posteriores.
- **Verificación:** Se ejecutó `pytest -v` comprobando que las 5 pruebas fallaran en rojo con `NotImplementedError`, y `pylint tests/` confirmando una calificación de `10.00/10`.
- **Commit relacionado:** `f1f8aab` (`test(hu-02): definir contrato en README y pruebas unitarias en rojo para extraer_monto`)

### Entrada 2

- **Fecha:** 2026-11-07
- **Prompt o sugerencia:** El asistente evaluó la posibilidad de integrar una llamada a un modelo de lenguaje (API externa) o librerías de procesamiento de lenguaje natural para interpretar jerga monetaria y estructurar de una vez la base de datos SQLite.
- **Decisión:** Rechazada
- **Por qué:** Rompería el alcance estricto de la Semana 5 (que exige implementar únicamente la unidad funcional de `HU-02`), introduciría dependencias externas innecesarias para un problema resoluble de forma determinista con la librería estándar (`re`) y agregaría riesgos de seguridad con claves `.env`.
- **Verificación:** Se verificó en `requirements.txt` que solo existan `pytest` y `pylint`, y que el módulo `src/parser_montos.py` funcione al 100% usando únicamente el módulo nativo `re`.
- **Commit relacionado:** `826d84c` (`feat(hu-02): implementar extraer_monto con regex determinista para pasar pruebas en verde`)

### Entrada 3

- **Fecha:** 2026-11-07
- **Prompt o sugerencia:** Usar una expresión regular básica `r"(\d+)\s*(lucas?|mil)?"` para extraer los dígitos y el multiplicador coloquial del texto ingresado.
- **Decisión:** Aceptada con cambios
- **Por qué:** Una expresión regular simple `(\d+)` dividiría erróneamente cifras con punto separador de miles como `"4.500"` en dos números (`"4"` y `"500"`), incumpliendo el caso límite del contrato. Se ajustó el patrón a `r"(?<!\d)(\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(lucas?|mil)\b)?"` y se agregó la limpieza del punto antes de convertir a `int`.
- **Verificación:** Se ejecutó `pytest -v`, comprobando que `test_extraer_monto_limite_punto_separador_miles` (`"4.500"` -> `4500`) y los casos con `"lucas"` y `"mil"` pasaran en verde.
- **Commit relacionado:** `826d84c` (`feat(hu-02): implementar extraer_monto con regex determinista para pasar pruebas en verde`)

### Entrada 4

- **Fecha:** 2026-11-07
- **Prompt o sugerencia:** Lanzar distintos mensajes de `ValueError` según la causa del fallo (por ejemplo, `"Texto vacío"` cuando la cadena no tiene caracteres y `"Monto ambiguo..."` cuando no hay dígitos).
- **Decisión:** Aceptada con cambios
- **Por qué:** El Escenario 2 de los criterios de aceptación de `HU-02` y el contrato definido en `README.md` especifican un mensaje único y estandarizado para cualquier entrada que no permita determinar un monto en cifras numéricas: `"Monto ambiguo. Por favor indique el valor en cifras numéricas"`. Se ajustó la validación para unificar la excepción e incluir la detección explícita de cuantificadores fraccionarios como `"media luca"`.
- **Verificación:** La prueba `test_extraer_monto_error_monto_ambiguo_sin_cifras` validó con `pytest.raises(ValueError, match=...)` que `"gasté media luca en dulces"` lance exactamente el mensaje del contrato.
- **Commit relacionado:** `826d84c` (`feat(hu-02): implementar extraer_monto con regex determinista para pasar pruebas en verde`)

### Entrada 5

- **Fecha:** 2026-11-07
- **Prompt o sugerencia:** Refactorizar `src/parser_montos.py` extrayendo constantes de nivel de módulo (`MENSAJE_MONTO_AMBIGUO`, `FACTOR_MILES`, `MULTIPLICADORES_MILES`, patrones regex precompilados) y dividiendo la lógica en tres funciones auxiliares privadas (`_normalizar_texto_entrada`, `_extraer_componentes_monto`, `_calcular_valor_entero`) con docstrings y anotaciones de tipos.
- **Decisión:** Aceptada
- **Por qué:** Elimina los valores mágicos (`1000`, cadenas literales repetidas), aplica el principio de responsabilidad única (SRP) manteniendo intacta la firma pública del contrato y permite cumplir el requisito no funcional de mantenibilidad (`RNF-05 >= 9.0/10` en `pylint`) sin tocar ni una línea de `tests/test_parser_montos.py`.
- **Verificación:** Se ejecutó `pytest -v` (`5 passed`), `pylint src/ tests/` obteniendo `10.00/10`, y `git status` confirmando que el archivo de pruebas no fue modificado.
- **Commit relacionado:** `ef6dfe1` (`refactor(hu-02): extraer constantes y funciones privadas en parser_montos cumpliendo PEP 8 (10/10 pylint)`)

### Entrada 6 (Semana 6 — Segunda revisión de seguridad con IA)

- **Fecha:** 2026-11-14
- **Prompt o sugerencia:** *"Revisa todo el código actual (`src/` y `tests/`) frente a los 5 criterios obligatorios de la Semana 6 (Inyección, Secretos, Contraseñas, Control de acceso y Dependencias). Entrega una tabla con Archivo/Línea, Severidad y Categoría, separando Problemas Reales de Sospechas / Falsos Positivos, y señala al menos 1 aspecto importante que la revisión automática no detectó."*
- **Decisión:** Aceptada con cambios
- **Por qué:** Se aceptaron los hallazgos reales verificados en el código: evasión de signos negativos en la expresión regular (`H-01`), falta de límite máximo de longitud contra ataques DoS/límite de 4.300 dígitos de `int()` (`H-02`) y dependencias sin versión exacta junto con la excepción `!.env.example` en `.gitignore` (`H-03`). En cambio, se descartaron tras verificación manual las sospechas de *Catastrophic Backtracking* ReDoS (`FP-02`), de `AttributeError` con `None` (`FP-03`) y los 5 avisos `S101` (`assert`) de `ruff` en `tests/` (`FP-01`).
- **Verificación:** Se comprobó cada hallazgo ejecutando `ruff check --select E,F,B,S .`, `pip-audit -r requirements.txt` (`No known vulnerabilities found`) y pruebas manuales con `"-20 lucas"` y cadenas masivas, documentando toda la clasificación en `revision_seguridad.md`.
- **Commit relacionado:** `19de0e3` (`chore(sec): configurar ruff (E,F,B,S), fijar versiones en requirements.txt y agregar .env.example`) y `191ef2e` (`docs(sec): diligenciar informe revision_seguridad.md con hallazgos, verificacion IA y commits`)

### Entrada 7 (Semana 6 — Corrección de hallazgos H-01 y H-02 y pruebas de abuso)

- **Fecha:** 2026-11-14
- **Prompt o sugerencia:** Corregir en `src/parser_montos.py` los hallazgos `H-01` (rechazo de montos con signo negativo mediante `PATRON_SIGNO_NEGATIVO`) y `H-02` (cota superior `LONGITUD_MAXIMA_TEXTO = 280` en `_normalizar_texto_entrada`), agregando 2 pruebas nuevas de abuso al final de `tests/test_parser_montos.py` sin alterar ninguna de las 5 pruebas de la Semana 5.
- **Decisión:** Aceptada
- **Por qué:** Cierra las vulnerabilidades de validación de entrada (`CWE-20`) y consumo no controlado de recursos (`CWE-400`) cumpliendo estrictamente el mensaje de error del contrato de `HU-02` y la regla de oro de no modificar pruebas existentes para que pasen.
- **Verificación:** Se ejecutó `pytest -v` pasando las 7 pruebas (`7 passed in 0.04s`) y se inspeccionó `git diff tests/test_parser_montos.py` confirmando que las líneas 1 a 38 de la Semana 5 permanecieron intactas (`+19/-0` líneas).
- **Commit relacionado:** `87ce079` (`fix(sec): mitigar abuso por montos negativos (H-01) y longitud excesiva DoS (H-02) con pruebas de abuso`)

### Entrada 8 (Semana 6 — Supervisión del agente en rama propia, docstrings y README)

- **Fecha:** 2026-11-14
- **Prompt o sugerencia:** Aplicar los cambios del agente en una rama dedicada (`fix/semana-6-seguridad`), completar los docstrings de las 4 funciones de `src/parser_montos.py` (qué hacen, qué reciben, qué devuelven y qué errores lanzan), revisar el `diff` con `ruff` y `pylint` antes de fusionar a `main`, y actualizar `README.md` con las 8 secciones obligatorias.
- **Decisión:** Aceptada con cambios
- **Por qué:** Al supervisar el primer borrador de docstrings generado por el agente antes de hacer commit en la rama, `ruff check` detectó una línea de 89 caracteres (`E501` en `src/parser_montos.py:28`) y `pylint` advirtió una línea en blanco final extra (`C0305` en `tests/test_parser_montos.py`). Se corrigieron ambos avisos antes de confirmar el commit en `fix/semana-6-seguridad` e integrarlo a `main` con `git merge --no-ff`.
- **Verificación:** Se ejecutaron `ruff check --select E,F,B,S src/` (`0` errores), `pylint src/ tests/` (`10.00/10`), y se probó el comando de ejecución del `README.md` (`python -c "..."`) verificando las salidas `20000` y `4500`.
- **Commit relacionado:** `3599d43` (`merge: integrar correcciones de seguridad H-01 y H-02 tras revisar diff`) y `fdc0225` (`docs(readme): actualizar README con las 8 secciones obligatorias de la semana 6`)

### Entrada 9 (Fase 1 - Hito 1A: Capa de persistencia SQLite parametrizada)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** Crear `src/database.py` con gestión contextual de conexiones SQLite, tablas `presupuesto` y `transacciones`, validación de presupuesto positivo (`HU-05`), filtrado por categoría (`HU-07`) y consultas 100% parametrizadas con `?`, junto con su suite de pruebas `tests/test_database.py`.
- **Decisión:** Aceptada
- **Por qué:** Garantiza persistencia 100% local (`RNF-02`) y previene vulnerabilidades de inyección SQL (`OWASP A03`) al separar estrictamente las sentencias SQL de los datos del usuario mediante tuplas de parámetros `?`. Además, incorpora la columna `es_ambiguo` para soportar la reclasificación con un clic exigida por el Escenario 2 de `HU-03`.
- **Verificación:** Se ejecutó `pytest -v` pasando las 13 pruebas unitarias y de abuso (incluyendo prueba de inyección SQL `'almuerzo'; DROP TABLE transacciones; --'`), `ruff check --select E,F,B,S .` con `0` avisos y `pylint src/ tests/` con calificación `>= 9.8/10`.
- **Commit relacionado:** `feat(db): implementar capa SQLite parametrizada para presupuesto y transacciones (HU-04, HU-05, HU-07)`

### Entrada 10 (Fase 1 - Hito 1B: Clasificador semántico híbrido y privacidad RNF-03)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** Implementar `src/clasificador.py` con extracción de concepto limpio (`HU-01`), clasificación automática en las 5 categorías fijas (`HU-03`), detección de conceptos ambiguos (`"pago asunto x 30000"` -> `"Gastos Varios"`, `es_ambiguo=True`), modo fallback offline (`RNF-02`) y sanitización de PII (`RNF-03`), junto con `tests/test_clasificador.py`.
- **Decisión:** Aceptada con cambios
- **Por qué:** Para cumplir `RNF-03` y `RNF-02` sin depender de conexión permanente a internet ni exponer datos del estudiante, se diseñó `construir_payload_llm` con expresiones regulares que anonimizan nombres propios, cédulas y direcciones físicas antes de cualquier llamada externa, y un motor léxico determinista sin tildes como fallback instantáneo.
- **Verificación:** Se ejecutó `pytest -v` pasando las 18 pruebas acumuladas (incluyendo simulación de `ConnectionError` del LLM y verificación de ausencia de PII en el payload), `ruff check --select E,F,B,S .` con `0` avisos y `pylint src/ tests/` con `10.00/10`.
- **Commit relacionado:** `feat(clasificador): implementar clasificacion tematica HU-03, fallback offline RNF-02 y anonimizacion RNF-03`

### Entrada 11 (Fase 2 - Hito 2: Servicios de negocio, alertas HU-06 y exportación CSV HU-08)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** Implementar `src/servicios.py` y `tests/test_servicios.py` integrando el parser de montos (`HU-02`), el clasificador (`HU-03`) y la base de datos SQLite para calcular el balance y la barra de progreso (`HU-04`), activar la confirmación preventiva cuando un gasto supera el 50% del presupuesto y la alerta `[ALERTA DE SOBREGIRO]` ante saldo negativo (`HU-06`), y exportar el archivo `gastos_<mes>_<anio>.csv` (`HU-08`).
- **Decisión:** Aceptada con cambios
- **Por qué:** Al verificar el cálculo del porcentaje del Escenario 1 de `HU-04` (`$220.000` sobre `$600.000` -> `36.6%`) y del Escenario 2 de `HU-06` (`$250.000` sobre `$400.000` -> `62.5%`), se observó que `round(220000 / 600000 * 100, 1)` redondeaba a `36.7%`. Se ajustó la función auxiliar `_calcular_porcentaje_truncado` con truncamiento a una cifra decimal (`int((numerador / denominador) * 1000) / 10.0`) para cumplir con exactitud ambos criterios Gherkin del documento de requisitos.
- **Verificación:** Se ejecutó `pytest -v` pasando las 23 pruebas acumuladas, `ruff check --select E,F,B,S .` con `0` avisos y `pylint src/ tests/` con `10.00/10`.
- **Commit relacionado:** `feat(servicios): implementar logica de negocio, alertas de sobregiro HU-06 y exportacion CSV HU-08`

### Entrada 12 (Fase 3 - Hito 3: Aplicación Web WSGI, Interfaz HTML/CSS y Pruebas de Integración)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** Implementar `app.py`, `templates/index.html`, `static/style.css` y `tests/test_app.py` con tarjetas métricas de balance (`HU-04`), formulario de presupuesto mensual (`HU-05`), barra de captura en lenguaje natural con `autofocus` (`HU-01`, `RNF-04`), modal de confirmación >50% y alerta roja de sobregiro (`HU-06`), tabla filtrable offline con reclasificación en un clic (`HU-03`, `HU-07`) y descarga de reporte CSV (`HU-08`).
- **Decisión:** Aceptada
- **Por qué:** Al implementar el servidor web sobre el estándar WSGI nativo de Python (`wsgiref`) con sanitización `html.escape` contra XSS, se logra un tiempo de carga inferior a `50 ms` (`RNF-01 < 1,2 s`), cero dependencias externas adicionales expuestas a CVEs en `pip-audit` y funcionamiento 100% offline (`RNF-02`).
- **Verificación:** Se ejecutó `pytest -v` pasando las 27 pruebas unitarias y de integración web, `ruff check --select E,F,B,S .` con `0` avisos y `pylint app.py src/ tests/` con calificación `10.00/10`.
- **Commit relacionado:** `feat(web): implementar aplicacion web local, interfaz responsiva HTML/CSS y pruebas de rutas (HU-01 a HU-08)`

### Entrada 13 (Fase 4 - Hito 4: Consolidación documental, auditoría final e integración del MVP)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** Actualizar `.gitignore` (excluyendo `data/`), `.env.example`, `README.md` (con las 8 secciones actualizadas para el MVP completo y comandos de inicio del servidor web `python app.py`) y `revision_seguridad.md` (documentando la verificación de consultas SQLite parametrizadas, escape XSS y anonimización `RNF-03`).
- **Decisión:** Aceptada
- **Por qué:** Asegura que toda la documentación técnica, de seguridad y de usuario refleje fielmente el estado final del MVP (27 pruebas automatizadas, 5 módulos Python con `10.00/10` en `pylint` y `0` avisos en `ruff check --select E,F,B,S .`).
- **Verificación:** Se ejecutaron `pytest -v` (`27 passed`), `ruff check --select E,F,B,S .` (`All checks passed!`) y `pylint app.py src/ tests/` (`10.00/10`).
- **Commit relacionado:** `docs(mvp): actualizar README, revision_seguridad y configuracion de entorno para el MVP completo`

### Entrada 14 (Semana 7 — Diseño de tablas de casos, particiones, valores límite y tabla de decisión con IA)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** *"Diseña en la Sección 1 de `registro_pruebas.md` las tablas de casos para `extraer_monto` (HU-02), `guardar_presupuesto` (HU-05), `clasificar_gasto` (HU-03) y la función multicondición `registrar_gasto_desde_texto` + `obtener_resumen_financiero` (HU-04 y HU-06), deduciendo cada valor esperado estrictamente de las historias de usuario (oráculo), incluyendo particiones válidas/inválidas, pares de valores límite, ambigüedades y la tabla de decisión de 6 reglas (R1 a R6)."*
- **Decisión:** Aceptada con cambios
- **Por qué:** Al revisar la propuesta inicial con las 5 preguntas de diseño (particiones, límites, origen del esperado, ambigüedades y reglas inventadas), se descartó una regla inventada que limitaba el presupuesto mensual máximo a `$10.000.000` (no existe en `HU-05`) y se documentaron explícitamente las ambigüedades reales: el tipo `bool` como subclase de `int` en Python, dos montos en una misma oración (`P-03`) y los bordes exactos del `50.0%` (`$200.000` vs `$200.001`) y saldo `$0` vs `-$1`.
- **Verificación:** Se contrastó cada fila de `registro_pruebas.md` contra los criterios Gherkin de `Puentes_Andres_S3_Requisitos.pdf` confirmando que todos los esperados provienen de la regla de negocio y no del código.
- **Commit relacionado:** `c2cd12b` (`docs(pruebas): definir reglas de negocio, particiones, limites y tabla de decision en registro_pruebas.md`)

### Entrada 15 (Semana 7 — Generación, auditoría con las 3 preguntas y pruebas de mutación manual)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** *"Genera con pytest la suite `tests/test_reglas_negocio_s7.py` usando `@pytest.mark.parametrize` con comentario por fila, `pytest.approx` para porcentajes y `pytest.raises` con el mensaje exacto. Luego audita cada prueba con las 3 preguntas (oráculo, fortaleza ante ruptura, redundancia) y ejecuta pruebas de mutación manual en `src/`."*
- **Decisión:** Aceptada con cambios
- **Por qué:** En la revisión con las 3 preguntas se corrigió el porcentaje esperado de `HU-04` Escenario 1 (`36.6%` por truncamiento del oráculo en vez de `36.7%` por `round()`), se eliminaron filas redundantes de la misma partición `'lucas'` y se fortalecieron las aserciones. Además, al aplicar la mutación manual `M-04` (desactivar `PATRON_CUANTIFICADORES_AMBIGUOS` en `src/parser_montos.py:49`), ninguna prueba falló inicialmente porque `"gasté media luca en dulces"` carecía de dígitos; se agregó el caso `"gasté 1 y media lucas en dulces"` para matar al mutante.
- **Verificación:** Se ejecutó `pytest -v` pasando las 67 pruebas (`67 passed in 1.17s`), se comprobaron y revirtieron con `git restore` las 4 mutaciones (`M-01` a `M-04`) en la Sección 3 de `registro_pruebas.md`, y se validó `ruff check --select E,F,B,S .` (`0` avisos) y `pylint app.py src/ tests/` (`10.00/10`).
- **Commit relacionado:** `a5b82cb`, `35cc138` y `5a174da` (`test(s7): documentar 4 pruebas de mutacion manual en registro_pruebas.md y agregar caso para M-04`)

### Entrada 16 (Semana 7 — Generación de datos sintéticos locales con casos difíciles en fixture de pytest)

- **Fecha:** 2026-11-22
- **Prompt o sugerencia:** *"Genera un `@pytest.fixture(name='dataset_gastos_sinteticos_locales')` en `tests/test_reglas_negocio_s7.py` con datos sintéticos 100% ficticios de contexto colombiano, sin datos de personas reales, que incluya casos difíciles: tildes múltiples, letra 'ñ', apóstrofo, espacios redundantes, texto vacío y valores en cero."*
- **Decisión:** Aceptada con cambios
- **Por qué:** El borrador inicial del test sobre el fixture verificaba únicamente `assert len(extraer_concepto(frase)) > 0` (prueba débil según la Pregunta 2). Se ajustó cada tupla del fixture para incluir el concepto exacto esperado según `HU-01` (ej. `"Fotocopias taller de sistemas"`, `"Almuerzo en restaurante D'Luxe Bistró"`) y se verificó con igualdad exacta `assert extraer_concepto(frase) == concepto_esp`, garantizando además que solo se usaran datos comerciales ficticios (`"Cafetería El Estudiante S.A.S. (Ficticia)"`, NIT `900.000.000-1`, teléfono `300-000-0000`).
- **Verificación:** Se ejecutó `pytest -v -k test_fixture_datos_sinteticos_locales_con_casos_dificiles` pasando al 100% y se documentó en la Sección 4 de `registro_pruebas.md`.
- **Commit relacionado:** `a5b82cb` y `35cc138` (`test(s7): fortalecer aserciones tras auditoria de las 3 preguntas y documentar secciones 2 y 4`)

### Entrada 17 (SDLC Etapa 1 — Análisis de Requisitos HU-09, HU-10, HU-11 y Diseño de Arquitectura)

- **Fecha:** 2026-11-25
- **Prompt o sugerencia:** *"Analizar las 4 limitaciones detectadas en el uso real de la aplicación (estética genérica, fricción para recuperar saldos negativos con ingresos extra, falta de gastos fijos mensuales y ausencia de control de créditos a cuotas) y diseñar las historias de usuario HU-09, HU-10 y HU-11 junto con la evolución del esquema SQLite y la ecuación de balance sin romper las 67 pruebas existentes."*
- **Decisión:** Aceptada
- **Por qué:** Al definir la ecuación `Saldo Disponible = Presupuesto Base + Ingresos Extra - Total Gastado`, se logra retrocompatibilidad total con las pruebas de las Semanas 5 a 7 (cuando `Ingresos Extra == 0`, la fórmula se reduce exactamente a `Presupuesto Base - Total Gastado`) a la vez que permite salir de sobregiros de forma natural. Asimismo, modelar `ingresos_extra`, `gastos_fijos` y `creditos` en tablas SQLite separadas mantiene la responsabilidad única y permite que al aplicar un gasto fijo o pagar una cuota se genere automáticamente su registro trazable en `transacciones`.
- **Verificación:** Se revisó la coherencia de los criterios de aceptación Gherkin de `HU-09`, `HU-10` y `HU-11` en `README.md` y se verificó con `pytest -v` que las 67 pruebas actuales sigan en verde antes de iniciar la implementación del backend.
- **Commit relacionado:** `docs(sdlc-etapa1): especificar HU-09, HU-10, HU-11 y arquitectura SQLite evolucionada en README y bitacora`

### Entrada 18 (SDLC Etapa 2 — Backend SQLite parametrizado y Servicios para HU-09, HU-10 y HU-11)

- **Fecha:** 2026-11-25
- **Prompt o sugerencia:** *"Implementar en `src/database.py` y `src/servicios.py` las tablas y operaciones parametrizadas para `ingresos_extra` (HU-09), `gastos_fijos` (HU-10) y `creditos` a cuotas (HU-11), junto con la suite `tests/test_evolucion_sdlc.py` y la actualización sincronizada de `registro_pruebas.md` y `revision_seguridad.md`."*
- **Decisión:** Aceptada
- **Por qué:** Todas las nuevas operaciones usan marcadores `?` y restricciones `CHECK` en SQLite, validando que `bool` no pase como `int` (`_es_entero_positivo`) y bloqueando pagos adicionales cuando `cuotas_pagadas >= total_cuotas` (`HU-11` Escenario 2). Además, la integración en `obtener_resumen_financiero` mantiene intactas las 67 pruebas previas y suma 6 nuevas pruebas para un total de 73 pruebas en verde.
- **Verificación:** Se ejecutó `pytest -v` pasando las 73 pruebas (`73 passed`), `ruff check --select E,F,B,S .` con `0` avisos y `pylint app.py src/ tests/` con `10.00/10`.
- **Commit relacionado:** `feat(sdlc-etapa2): implementar backend SQLite y servicios para ingresos extra, gastos fijos y creditos (HU-09 a HU-11)`

## Resumen

| Decisión | Cantidad |
|---|---|
| Aceptadas | 8 |
| Aceptadas con cambios | 9 |
| Rechazadas | 1 |

## Errores que atraparon las pruebas

Durante el diseño de la expresión regular en la Semana 5, una captura ingenua de dígitos (`\d+`) habría interpretado el caso límite `"4.500"` como dos coincidencias numéricas separadas (`"4"` y `"500"`), haciendo fallar la prueba `test_extraer_monto_limite_punto_separador_miles` (que esperaba el entero `4500`). Asimismo, en la Semana 6, las nuevas pruebas de abuso (`test_extraer_monto_abuso_monto_negativo` y `test_extraer_monto_abuso_longitud_excesiva`) permitieron comprobar que entradas maliciosas como `"gasté -20 lucas en almuerzo"` (que antes se convertía silenciosamente en `20000` positivo) o payloads de >500 caracteres ahora son rechazados de forma determinista con el `ValueError` exacto del contrato.

## Reflexión final (5 a 8 líneas)

El asistente de IA fue de gran utilidad para estructurar el contrato formal de `HU-02`, diseñar expresiones regulares para jerga colombiana y realizar en la Semana 6 una segunda auditoría de seguridad que reveló un defecto lógico sutil con montos negativos (`H-01`) y riesgos de DoS por longitud (`H-02`).
Trabajar bajo TDD estricto y supervisar al agente en una rama dedicada (`fix/semana-6-seguridad`) demostró que las sugerencias de la IA nunca deben aceptarse a ciegas: fue indispensable verificar manualmente cada hallazgo para descartar falsos positivos como la sospecha de ReDoS (`FP-02`) o los avisos `S101` en `pytest`.
Además, la combinación de `pytest`, `ruff --select E,F,B,S`, `pylint` (`10.00/10`) y `pip-audit` actuó como un filtro objetivo que atrapó desde excesos de longitud de línea (`E501`) hasta bordes semánticos del dominio sin alterar ni una sola línea de las pruebas originales.
Para los próximos incrementos con SQLite y endpoints web, mantendré este flujo de trabajo en ramas con revisión de `diff`, pruebas de abuso previas y auditoría continua de dependencias.

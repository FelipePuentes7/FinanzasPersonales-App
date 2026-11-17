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

## Resumen

| Decisión | Cantidad |
|---|---|
| Aceptadas | 2 |
| Aceptadas con cambios | 2 |
| Rechazadas | 1 |

## Errores que atraparon las pruebas

Durante el diseño de la expresión regular para pasar de la fase Roja a la fase Verde, una captura ingenua de dígitos (`\d+`) habría interpretado el caso límite `"4.500"` como dos coincidencias numéricas separadas (`"4"` y `"500"`), haciendo fallar la prueba `test_extraer_monto_limite_punto_separador_miles` (que esperaba el entero `4500`). Asimismo, la prueba `test_extraer_monto_error_monto_ambiguo_sin_cifras` con la entrada `"gasté media luca en dulces"` obligó a validar explícitamente cuantificadores fraccionarios en texto y verificar la coincidencia exacta del mensaje de `ValueError` exigido por `HU-02`.

## Reflexión final (5 a 8 líneas)

El asistente de IA fue de gran utilidad para estructurar rápidamente el contrato formal de `HU-02`, diseñar expresiones regulares precisas para jerga colombiana y aplicar refactorizaciones alineadas con PEP 8 hasta alcanzar 10.00/10 en `pylint`.
Trabajar bajo un flujo TDD estricto invirtió positivamente el control de calidad: al fijar primero las 5 pruebas unitarias en el Commit 1, las pruebas actuaron como una red de seguridad inamovible que impidió introducir código innecesario o romper casos límite como `"1 LUCA"` y `"4.500"`.
Además, la restricción de no modificar las pruebas durante el Commit 2 y el Commit 3 nos obligó a pensar cuidadosamente los casos borde y la calidad del archivo de tests desde el inicio.
Para la próxima funcionalidad, mantendré esta misma disciplina de precompilar patrones y definir constantes de dominio desde la etapa de diseño para reducir la deuda técnica entre la implementación en verde y la refactorización.

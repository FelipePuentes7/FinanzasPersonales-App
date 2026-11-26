# Informe de revisión de código y seguridad

Proyecto: Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)
Estudiante: Andrés Felipe Puentes
Fecha: 2026-11-14 
Commit revisado: `ab006fc` (código funcional de `src/parser_montos.py` del commit `ef6dfe1`)

## 1. Herramientas y criterios

- **Linter:** `ruff 0.11.2` con las reglas `[E, F, B, S]` (configuración en `pyproject.toml`) y `pylint 4.1.4` (`10.00/10`).
- **Auditoría de dependencias:** `pip-audit 2.9.0` — resultado: sin vulnerabilidades conocidas (`No known vulnerabilities found`).
- **Lista de revisión:** la de la semana 6 (corrección y pruebas, diseño y legibilidad, seguridad).
- **Revisión con IA:** Google Antigravity (Modo Agente y Chat) con el prompt de auditoría de seguridad de la semana 6 (ver sección 3).

### Puntos de seguridad revisados

| Punto | ¿Aplica? | Resultado |
|---|---|---|
| Inyección (consultas con parámetros) | Sí (5 tablas SQLite en `src/database.py`: `presupuesto`, `transacciones`, `ingresos_extra`, `gastos_fijos`, `creditos`; parser regex en `src/parser_montos.py` y escape HTML en `app.py`) | Todas las sentencias `SELECT`, `INSERT`, `UPDATE` y `DELETE` de las 5 tablas usan exclusivamente parámetros `?` (0 concatenaciones SQL). En `app.py` se aplica `html.escape` contra XSS. |
| Secretos (código, historial, .gitignore, .env.example) | Sí | Sin claves expuestas en el código ni en el historial (`git log -p`). `.env` y `data/` están en `.gitignore`, existe `.env.example` y `src/clasificador.py` anonimiza PII (`RNF-03`). |
| Contraseñas (scrypt, bcrypt o argon2 con sal) | No, porque la aplicación es una herramienta monousuario de ejecución 100% local (sección 7 de requisitos descarta autenticación por sesión). | No aplica al alcance del proyecto por diseño monousuario local. |
| Control de acceso (rol verificado y prueba de abuso) | Parcialmente (frontera de validación de dominio y pruebas de abuso sobre entradas web y base de datos) | Se implementaron validaciones de frontera, `CHECK` constraints en SQLite y pruebas de abuso para montos negativos (`H-01`), payloads masivos DoS (`H-02`), presupuestos/ingresos/gastos fijos no positivos (`HU-05`, `HU-09`, `HU-10`), bloqueo de pago en créditos saldados (`HU-11`), inyección SQL y exportación CSV vacía (`HU-08`). |
| Dependencias (existen, necesarias, versión fijada, pip-audit) | Sí | Versiones exactas (`==`) fijadas en `requirements.txt` y `pip-audit` confirmó `0` vulnerabilidades (`No known vulnerabilities found`). |

## 2. Tabla de hallazgos

| Id | Archivo y línea | Problema | Categoría (OWASP o tipo) | Severidad | Corrección | Commit |
|---|---|---|---|---|---|---|
| H-01 | `src/parser_montos.py:20` y `src/parser_montos.py:85` | Expresión regular ignoraba el signo `-` previo al número, convirtiendo montos negativos (`"-20 lucas"`) en positivos (`20000`). | A04 Diseño Inseguro / CWE-20 Validación de entrada | Media | Agregar `PATRON_SIGNO_NEGATIVO` en `_normalizar_texto_entrada` para rechazar cifras negativas y añadir prueba de abuso. | `87ce079` |
| H-02 | `src/parser_montos.py:37` | Ausencia de cota superior de longitud en `texto`, permitiendo payloads masivos (riesgo de DoS por consumo de CPU/memoria y excepción de límite de dígitos de Python). | A04 Diseño Inseguro / CWE-400 Consumo de recursos (DoS) | Media | Definir constante `LONGITUD_MAXIMA_TEXTO = 280`, validar `len(texto)` antes de evaluar regex y añadir prueba de abuso. | `87ce079` |
| H-03 | `requirements.txt:1-2` y `.gitignore:3` | Dependencias con rangos abiertos (`>=`) sin fijar versión exacta y regla `.env.*` que bloqueaba el archivo `.env.example`. | A06 Componentes vulnerables / Configuración segura | Baja | Fijar versiones exactas (`==`), auditar con `pip-audit`, crear `.env.example` y agregar `!.env.example` en `.gitignore`. | `19de0e3` |

**Severidad:** alta (permite acceder o cambiar datos sin permiso, o expone secretos), media (error probable o riesgo con condiciones), baja (estilo o mantenibilidad).

### Avisos del linter no corregidos

| Regla | Archivo y línea | Por qué se mantiene |
|---|---|---|
| `S101` | `tests/test_parser_montos.py:11, 16, 17, 23, 29` | `assert` es la forma estándar de comprobar resultados en `pytest`. Además, las 5 pruebas unitarias de la Semana 5 se mantienen intactas por regla estricta de TDD. En `src/` hay `0` avisos. |

## 3. Revisión con IA

**Prompt usado:** *"Revisa todo el código actual (`src/` y `tests/`) frente a los 5 criterios obligatorios de la Semana 6 (Inyección, Secretos, Contraseñas, Control de acceso y Dependencias). Entrega una tabla con Archivo/Línea, Severidad y Categoría, separando Problemas Reales de Sospechas / Falsos Positivos, y señala al menos 1 aspecto importante que la revisión automática no detectó."* (Ver Entrada 6 en [`bitacora_ia.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/bitacora_ia.md)).

| Hallazgo de la IA | ¿Real o falso positivo? | Cómo lo verifiqué |
|---|---|---|
| **H-01:** Evasión de montos negativos (`"-20 lucas"` evaluado como `20000`) en `src/parser_montos.py:20`. | **Real** | Ejecuté el caso `"gasté -20 lucas en almuerzo"` sobre el código de la Semana 5 y comprobé que `(?<!\d)` ignoraba el carácter `-` y retornaba `20000`. Se corrigió y verificó con `test_extraer_monto_abuso_monto_negativo`. |
| **H-02:** Falta de límite de longitud en `_normalizar_texto_entrada` (`src/parser_montos.py:37`). | **Real** | Comprobé que no existía validación `len(texto)`, permitiendo procesar cadenas de longitud arbitraria. Se corrigió con `LONGITUD_MAXIMA_TEXTO = 280` y `test_extraer_monto_abuso_longitud_excesiva`. |
| **H-03:** Versiones no fijadas con `==` en `requirements.txt` y bloqueo de `.env.example` por `.env.*`. | **Real** | Inspeccioné `requirements.txt` (usaba `>=`) y comprobé con `git status` que `.env.*` en `.gitignore` ocultaba `.env.example` sin la excepción `!.env.example`. |
| **FP-01:** 5 avisos `S101` (`Use of assert detected`) reportados por `ruff` en `tests/test_parser_montos.py`. | **Falso positivo (contexto de pruebas)** | Verifiqué que los 5 `assert` están exclusivamente dentro de `tests/test_parser_montos.py` (donde `pytest` reescribe el AST para aserciones) y que en `src/parser_montos.py` no se usa ningún `assert`. |
| **FP-02:** Sospecha de *Catastrophic Backtracking* (ReDoS - CWE-1333) en `PATRON_MONTO_COLOQUIAL` (`(\d{1,3}(?:\.\d{3})+|\d+)`). | **Falso positivo** | Analicé manualmente la expresión regular: el subgrupo repetido `(?:\.\d{3})+` exige un punto literal `.` entre bloques de 3 dígitos. Al ser `.` y `\d` conjuntos disjuntos, no hay ambigüedad exponencial de backtracking. |
| **FP-03:** Sospecha de `AttributeError` si `texto` recibe `None` al invocar `texto.strip()`. | **Falso positivo** | Verifiqué la línea 37 (`if not isinstance(texto, str) or not texto.strip():`): el cortocircuito del operador `or` evalúa primero `isinstance(texto, str)` y lanza el `ValueError` del contrato sin evaluar `.strip()`. |

**Lo que la IA no encontró:** Ni el linter automático (`ruff` / `pylint`) ni un análisis superficial de sintaxis detectaron dos detalles semánticos clave del dominio y de Python 3.12:
1. **Invariante parcialmente inalcanzable en `src/parser_montos.py:85`:** La validación `if valor_base <= 0:` fue escrita asumiendo que atraparía tanto el cero como números negativos; sin embargo, al no capturar el signo `-` en la expresión regular, la rama `< 0` era código muerto inalcanzable.
2. **Fuga de excepción interna de Python (`CVE-2020-10735`) que rompía el contrato:** Si un usuario ingresaba un número de más de 4.300 dígitos, `int(cifra_str)` en la línea 83 lanzaba un `ValueError` propio de Python (`Exceeds the limit (4300 digits) for integer string conversion`) cuyo mensaje en inglés violaba el contrato de `HU-02` (que exige siempre el mensaje exacto `"Monto ambiguo. Por favor indique el valor en cifras numéricas"`). Al acotar la entrada con `LONGITUD_MAXIMA_TEXTO = 280`, ambos riesgos quedaron neutralizados.

## 4. Pendientes

| Pendiente | Por qué no se corrigió todavía | Plan |
|---|---|---|
| Consultas SQL parametrizadas en SQLite | El alcance de las Semanas 5 y 6 comprende únicamente el módulo de dominio `HU-02` (`src/parser_montos.py`) sin capa de persistencia aún. | En el incremento de persistencia (`HU-01`/`HU-03`), usar marcadores `?` en `sqlite3` / ORM sin interpolar cadenas (`f-strings`) y agregar prueba de inyección SQL. |
| Autenticación y control de acceso en endpoints web | Aún no se ha integrado la capa HTTP (Flask/FastAPI) ni gestión de usuarios. | Validar esquemas de entrada con límites estrictos y verificar permisos por sesión en cada endpoint restringido. |

**Claves expuestas:** Ninguna.

# Registro de pruebas: tabla de casos y pruebas de la IA

Proyecto: Asistente Web para Registro y Análisis de Gastos Personales mediante IA (FinanzasPersonales-App)
Estudiante: Andrés Felipe Puentes Rivera
Fecha: 2026-11-22

---

## 1. Tabla de casos

### Regla 1: `extraer_monto(texto: str) -> int` — Normalización de jerga monetaria colombiana y cifras a entero en COP (`HU-02`)

**Regla completa (el oráculo):**
Según la historia de usuario **`HU-02`** (*"Como estudiante universitario, quiero que el sistema reconozca términos como 'lucas' o 'mil' para evitar digitar manualmente todos los ceros de una cantidad"*) y las restricciones de validación de entrada (`1 <= len(texto) <= 280`):
1. **Escenario 1 (Procesamiento de modismos y formatos numéricos):** Cuando el texto contiene una única cifra entera positiva acompañada de los términos coloquiales `'luca'`, `'lucas'` o `'mil'` (insensible a mayúsculas/minúsculas), el sistema multiplica el valor por `1000` y retorna el entero en pesos colombianos (COP). Si la cifra no tiene multiplicador coloquial (o usa punto `.` como separador de bloques de 3 dígitos, ej. `'4.500'`), retorna el valor entero equivalente (`4500`).
2. **Escenario 2 (Cifra ambigua o no convertible):** Si el texto está vacío, supera los `280` caracteres, carece de cifras numéricas, utiliza fracciones textuales (`'media luca'`), contiene múltiples montos distintos en la misma oración o el valor numérico es menor o igual a `0` (cero o negativo), el sistema detiene el procesamiento y lanza `ValueError` con el mensaje exacto: `"Monto ambiguo. Por favor indique el valor en cifras numéricas"`.

| Técnica | Partición o límite | Entrada (`texto`) | Esperado (Oráculo) | Prueba que lo cubre |
|---|---|---|---|---|
| Partición válida | Modismo coloquial plural (`lucas`) | `"20 lucas de gasolina para la moto"` | `20000` | `test_extraer_monto_particiones_y_limites_validos[20 lucas de gasolina para la moto-20000]` |
| Partición válida | Modismo coloquial (`mil`) | `"almuerzo ejecutivo 15 mil"` | `15000` | `test_extraer_monto_particiones_y_limites_validos[almuerzo ejecutivo 15 mil-15000]` |
| Partición válida | Cifra con punto separador de miles | `"fotocopias taller 4.500"` | `4500` | `test_extraer_monto_particiones_y_limites_validos[fotocopias taller 4.500-4500]` |
| Partición válida | Cifra directa sin modismo | `"almuerzo corriente 14000"` | `14000` | `test_extraer_monto_particiones_y_limites_validos[almuerzo corriente 14000-14000]` |
| Límite (Borde inferior positivo) | Primer valor positivo válido (`monto = 1`) | `"ajuste 1"` | `1` | `test_extraer_monto_particiones_y_limites_validos[ajuste 1-1]` |
| Límite (Borde inferior con modismo) | Unidad mínima en mayúsculas (`1 LUCA`) | `"1 LUCA"` | `1000` | `test_extraer_monto_particiones_y_limites_validos[1 LUCA-1000]` |
| Límite (Borde superior de longitud) | Último largo permitido (`len = 280`) | `"1000 " + ("a" * 275)` | `1000` | `test_extraer_monto_particiones_y_limites_validos[texto_entrada6-1000]` |
| Límite (Borde inferior inválido) | Último valor no positivo (`monto = 0`) | `"descuento 0"` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[descuento 0]` |
| Límite (Borde negativo) | Primer entero negativo (`monto = -1`) | `"ajuste -1"` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[ajuste -1]` |
| Límite (Borde longitud excedida) | Primer largo inválido (`len = 281`) | `"1000 " + ("a" * 276)` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[texto_invalido3]` |
| Partición inválida | Fracción coloquial sin dígitos (`HU-02` Esc. 2) | `"gasté media luca en dulces"` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[gasté media luca en dulces]` |
| Partición inválida (Mutación M-04) | Cifra combinada con cuantificador fraccionario (`1 y media lucas`) | `"gasté 1 y media lucas en dulces"` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[gasté 1 y media lucas en dulces]` |
| Partición inválida | Múltiples montos en una frase (`P-03`) | `"almuerzo 15 mil y gasolina 10 mil"` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[almuerzo 15 mil y gasolina 10 mil]` |
| Partición inválida | Texto vacío o solo espacios | `""` / `"   "` | `ValueError` | `test_extraer_monto_particiones_y_limites_invalidos[]` |

**Ambigüedades encontradas:**
1. **Dos montos en la misma frase (Pregunta `P-03` del documento de requisitos):** La historia `HU-02` no especificaba si `"almuerzo 15 mil y gasolina 10 mil"` debía sumarse o rechazarse. Se definió en el contrato que cada registro corresponde a una única transacción; por tanto, si hay dos o más cifras en la frase, se rechaza como `"Monto ambiguo..."`.
2. **Monto igual a cero (`"0"` o `"0 lucas"`):** Aunque `"0"` es un dígito numérico, en el dominio contable de gastos personales no existe un gasto de `$0` COP. Se resolvió que el límite inferior válido es `1` peso (`> 0`), mientras que `0` pertenece a la partición inválida.

---

### Regla 2: `guardar_presupuesto(monto_mensual: int, ruta_db) -> int` — Validación y actualización del tope presupuestal (`HU-05`)

**Regla completa (el oráculo):**
Según la historia de usuario **`HU-05`** (*"Como usuario, quiero definir y modificar mi tope de presupuesto mensual en un panel lateral de ajustes para mantener alineado el saldo disponible con mis ingresos del mes"*):
1. **Escenario 1 (Modificación exitosa):** Cuando el usuario introduce un número entero positivo mayor a cero (ej. `750000`), el sistema actualiza la base de datos local SQLite y retorna el nuevo tope presupuestal configurado.
2. **Escenario 2 (Presupuesto negativo o cero):** Cuando el usuario introduce un valor menor o igual a cero (ej. `-50000` o `0`) o un tipo de dato no entero, el sistema rechaza la operación y lanza `ValueError` con el mensaje exacto: `"El presupuesto mensual debe ser un número positivo mayor a cero"`.

| Técnica | Partición o límite | Entrada (`monto_mensual`) | Esperado (Oráculo) | Prueba que lo cubre |
|---|---|---|---|---|
| Partición válida | Presupuesto mensual típico de estudiante | `600000` | `600000` | `test_guardar_presupuesto_particiones_y_limites_validos[600000-600000]` |
| Partición válida | Actualización de tope presupuestal (`HU-05` Esc. 1) | `750000` | `750000` | `test_guardar_presupuesto_particiones_y_limites_validos[750000-750000]` |
| Límite (Borde inferior válido) | Primer entero positivo después de cero (`1`) | `1` | `1` | `test_guardar_presupuesto_particiones_y_limites_validos[1-1]` |
| Límite (Borde superior inválido) | Último entero no positivo antes de uno (`0`) | `0` | `ValueError` | `test_guardar_presupuesto_particiones_y_limites_invalidos[0]` |
| Límite (Borde negativo inmediato) | Primer entero negativo (`-1`) | `-1` | `ValueError` | `test_guardar_presupuesto_particiones_y_limites_invalidos[-1]` |
| Partición inválida | Monto negativo de `HU-05` Escenario 2 | `-50000` | `ValueError` | `test_guardar_presupuesto_particiones_y_limites_invalidos[-50000]` |
| Partición inválida | Tipo booleano (`True` es subclase de `int` en Python) | `True` | `ValueError` | `test_guardar_presupuesto_particiones_y_limites_invalidos[True]` |

**Ambigüedades encontradas:**
En Python, el tipo `bool` hereda de `int` (`isinstance(True, int) == True` y `int(True) == 1`). Si solo se validara `isinstance(monto, int) and monto > 0`, pasar `True` se guardaría como un presupuesto de `$1` COP. Con base en la regla de negocio (*"número positivo mayor a cero"*), se clasificó `bool` como partición inválida explícita.

---

### Regla 3: `clasificar_gasto(texto: str) -> tuple[str, bool]` — Clasificación temática automática y detección de ambigüedad (`HU-03`)

**Regla completa (el oráculo):**
Según la historia de usuario **`HU-03`** (*"Como usuario, quiero que la aplicación asigne automáticamente la categoría correspondiente a cada compra para prescindir de menús desplegables manuales en cada registro"*):
1. **Escenario 1 (Inferencia correcta de categoría):** Toda descripción con contexto semántico reconocible se clasifica en una de las 4 categorías específicas (`'Transporte/Moto'`, `'Alimentación'`, `'Estudio'`, `'Ocio'`) con bandera `es_ambiguo = False`, ignorando mayúsculas y tildes.
2. **Escenario 2 (Concepto ambiguo no tipificado):** Si la descripción carece de contexto semántico reconocible (ej. `"pago asunto x 30000"`), el sistema asigna temporalmente la categoría `'Gastos Varios'` y marca `es_ambiguo = True` para resaltar la fila en la tabla web. Si el texto está vacío (`""`), lanza `ValueError`.

| Técnica | Partición o límite | Entrada (`texto`) | Esperado (Oráculo) | Prueba que lo cubre |
|---|---|---|---|---|
| Partición válida | Contexto movilidad / repuestos (`Transporte/Moto`) | `"cambio pastillas de freno y aceite moto 45000"` | `("Transporte/Moto", False)` | `test_clasificar_gasto_particiones[moto]` |
| Partición válida | Contexto comida con tildes y `ñ` (`Alimentación`) | `"almuerzo navideño y café en cafetería 18000"` | `("Alimentación", False)` | `test_clasificar_gasto_particiones[alimentacion]` |
| Partición válida | Contexto académico (`Estudio`) | `"fotocopias taller de sistemas 4500"` | `("Estudio", False)` | `test_clasificar_gasto_particiones[estudio]` |
| Partición válida | Contexto recreación / vestuario (`Ocio`) | `"compra chaqueta y boleta cine 95000"` | `("Ocio", False)` | `test_clasificar_gasto_particiones[ocio]` |
| Partición válida (Ambiguo) | Sin contexto reconocible (`HU-03` Esc. 2) | `"pago asunto x 30000"` | `("Gastos Varios", True)` | `test_clasificar_gasto_particiones[ambiguo]` |
| Partición inválida | Cadena vacía o solo espacios en blanco | `""` / `"   "` | `ValueError` | `test_clasificar_gasto_texto_vacio_lanza_error` |

**Ambigüedades encontradas:**
Cuando el usuario escribe palabras con o sin tilde (ej. `"cafetería"` vs `"cafeteria"`, `"mecánico"` vs `"mecanico"`) o con eñe (`"daño"`), el oráculo exige la misma categoría. Se resolvió normalizando signos diacríticos (NFD) antes de buscar palabras clave completas (`\b...\b`).

---

### Regla 4 (Multicondición con Tabla de Decisión): `registrar_gasto_desde_texto` y `obtener_resumen_financiero` — Evaluación combinada de presupuesto, confirmación >50% y alerta de sobregiro (`HU-04` y `HU-06`)

**Regla completa (el oráculo):**
Según **`HU-04`** (Escenarios 1 y 2) y **`HU-06`** (Escenarios 1 y 2), al procesar un gasto válido de monto $M$ sobre una cuenta con gastos previos acumulados $G_{prev}$:
1. Si **no hay presupuesto mensual configurado** ($P = \text{None}$), el gasto se registra normalmente (`registrado = True`), sin pedir confirmación (`requiere_confirmacion = False`) y sin alerta de sobregiro (`alerta_sobregiro = None`).
2. Si **hay presupuesto activo** ($P > 0$), el monto del gasto **supera estrictamente el 50% del presupuesto** ($M > 0.5 \times P$) y el usuario **no ha confirmado** (`confirmado = False`), el sistema **no** registra la transacción (`registrado = False`), activa `requiere_confirmacion = True` y emite el mensaje: `"Atención: Este gasto representa el X.X% de su presupuesto mensual. ¿Desea confirmar el registro? (Confirmar / Cancelar)"`.
3. Si el gasto es **menor o igual al 50% del presupuesto** ($M \le 0.5 \times P$) **o** el usuario **ya confirmó** (`confirmado = True`), el sistema registra la transacción (`registrado = True`).
4. Una vez registrado el gasto con presupuesto activo, si el **nuevo saldo restante es estrictamente negativo** ($P - (G_{prev} + M) < 0$), el sistema activa la alerta `"[ALERTA DE SOBREGIRO] Este gasto supera su saldo restante"` (`en_sobregiro = True`); si el saldo resultante es mayor o igual a cero ($\ge 0$), no hay alerta de sobregiro (`None`).

#### Tabla de Decisión (Combinación de Condiciones C1, C2, C3 y C4)

| Condiciones y Acciones | R1 (Sin presupuesto) | R2 (>50% sin confirmar) | R3 ($\le 50\%$ y saldo $\ge 0$) | R4 ($\le 50\%$ y saldo $< 0$) | R5 (>50% confirmado y saldo $\ge 0$) | R6 (>50% confirmado y saldo $< 0$) |
|---|---|---|---|---|---|---|
| **C1:** ¿Presupuesto $P$ configurado? | No | Sí | Sí | Sí | Sí | Sí |
| **C2:** ¿Monto $M > 0.5 \times P$ (> 50%)? | — *(No importa)* | Sí | No | No | Sí | Sí |
| **C3:** ¿Usuario confirmó (`confirmado=True`)? | — *(No importa)* | No | — *(No importa)* | — *(No importa)* | Sí | Sí |
| **C4:** ¿Nuevo saldo $P - (G_{prev} + M) < 0$? | — *(No importa)* | — *(No importa)* | No | Sí | No | Sí |
| **Acción A1 (`registrado` en SQLite):** | **`True`** | **`False`** | **`True`** | **`True`** | **`True`** | **`True`** |
| **Acción A2 (`requiere_confirmacion`):** | **`False`** | **`True`** | **`False`** | **`False`** | **`False`** | **`False`** |
| **Acción A3 (`alerta_sobregiro` activa):** | **`None`** | **`None`** | **`None`** | **`[ALERTA DE SOBREGIRO]...`** | **`None`** | **`[ALERTA DE SOBREGIRO]...`** |

#### Tabla de Casos y Valores Límite de la Función Multicondición (`HU-04` y `HU-06`)

| Técnica | Partición o límite | Entrada ($P$, $G_{prev}$, `texto`, `confirmado`) | Esperado (Oráculo) | Prueba que lo cubre |
|---|---|---|---|---|
| Tabla de decisión (R1) | Sin presupuesto inicializado (`HU-04` Esc. 2) | $P=\text{None}, G_{prev}=0$, `"almuerzo 14000"`, `False` | `registrado=True, req_conf=False, sobregiro=None` | `test_tabla_decision_alertas_hu06[R1_sin_presupuesto]` |
| Tabla de decisión (R2) | Gasto $>50\%$ sin confirmar (`HU-06` Esc. 2: $62.5\%$) | $P=400000, G_{prev}=0$, `"reparación motora 250000"`, `False` | `registrado=False, req_conf=True, pct=62.5` | `test_tabla_decision_alertas_hu06[R2_mayor_50_sin_confirmar]` |
| Tabla de decisión (R3) | Gasto $\le 50\%$ con saldo positivo (`HU-04` Esc. 1: $36.6\%$) | $P=600000, G_{prev}=206000$, `"almuerzo 14000"`, `False` | `registrado=True, req_conf=False, saldo=380000, pct=36.6` | `test_tabla_decision_alertas_hu06[R3_normal_saldo_positivo]` |
| Tabla de decisión (R4) | Gasto $\le 50\%$ que causa sobregiro (`HU-06` Esc. 1: $-\$15.000$) | $P=400000, G_{prev}=320000$, `"compra chaqueta 95000"`, `False` | `registrado=True, req_conf=False, sobregiro=ALERTA` | `test_tabla_decision_alertas_hu06[R4_menor_50_con_sobregiro]` |
| Tabla de decisión (R5) | Gasto $>50\%$ confirmado con saldo positivo | $P=400000, G_{prev}=0$, `"reparación motora 250000"`, `True` | `registrado=True, req_conf=False, sobregiro=None` | `test_tabla_decision_alertas_hu06[R5_mayor_50_confirmado_sin_sobregiro]` |
| Tabla de decisión (R6) | Gasto $>50\%$ confirmado que además sobregira | $P=400000, G_{prev}=200000$, `"reparación motora 250000"`, `True` | `registrado=True, req_conf=False, sobregiro=ALERTA` | `test_tabla_decision_alertas_hu06[R6_mayor_50_confirmado_con_sobregiro]` |
| Límite (Borde 50.0% exacto) | Último valor que NO pide confirmación ($M = 50.0\%$ de $P$) | $P=400000, G_{prev}=0$, `"repuesto moto 200000"`, `False` | `registrado=True, req_conf=False, pct=50.0` | `test_limites_umbral_50_y_sobregiro[limite_exacto_50_pct]` |
| Límite (Borde 50.1%) | Primer valor que SÍ pide confirmación ($M = 200001 > 50\%$) | $P=400000, G_{prev}=0$, `"repuesto moto 200001"`, `False` | `registrado=False, req_conf=True` | `test_limites_umbral_50_y_sobregiro[limite_supera_50_pct_por_1_peso]` |
| Límite (Borde saldo = 0) | Último valor sin sobregiro ($\text{Nuevo saldo} = 0$) | $P=400000, G_{prev}=320000$, `"chaqueta 80000"`, `False` | `registrado=True, sobregiro=None, saldo=0` | `test_limites_umbral_50_y_sobregiro[limite_saldo_exacto_cero]` |
| Límite (Borde saldo = -1) | Primer valor con sobregiro ($\text{Nuevo saldo} = -1$) | $P=400000, G_{prev}=320000$, `"chaqueta 80001"`, `False` | `registrado=True, sobregiro=ALERTA, saldo=-1` | `test_limites_umbral_50_y_sobregiro[limite_sobregiro_por_1_peso]` |

**Ambigüedades encontradas:**
1. **Borde exacto del 50% (`$200.000` sobre un presupuesto de `$400.000`):** La historia `HU-06` dice *"consumo de más del 50% del presupuesto"*. Esto significa desigualdad estricta (`>`): exactamente el `50.0%` (`$200.000`) **no** dispara el modal de confirmación, mientras que `$200.001` (`> 50%`) **sí** lo dispara.
2. **Borde exacto de saldo `$0` COP:** La historia `HU-06` Escenario 1 define la alerta por *"saldo negativo"*. Por tanto, quedar con saldo exacto de `$0` COP **no** es sobregiro; el sobregiro inicia en `-$1` COP (`saldo < 0`).

---

## 2. Pruebas de la IA descartadas o corregidas

**Prompt usado:** *"Genera con pytest la suite de pruebas en `tests/test_reglas_negocio_s7.py` a partir de las 4 reglas de negocio (oráculo) y las tablas de particiones, valores límite y tabla de decisión de `registro_pruebas.md`. Usa `@pytest.mark.parametrize` con comentario explicativo por fila, `pytest.approx` para porcentajes decimales y `pytest.raises` con el tipo y mensaje exacto de error, sin modificar el código fuente. Luego audita cada prueba con las 3 preguntas de revisión."* (Ver Entradas 14 y 15 en [`bitacora_ia.md`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/bitacora_ia.md)).

| Prueba generada | Decisión | Por qué | En su lugar |
|---|---|---|---|
| `test_fixture_datos_sinteticos`: `assert len(extraer_concepto(frase)) > 0` | **Corregida** | **Pregunta 2 (Débil):** Solo comprobaba que la longitud fuera mayor a cero; pasaría aunque `extraer_concepto` no limpiara el monto numérico ni los espacios redundantes o devolviera siempre `"X"`. | Se agregó el concepto exacto del oráculo en cada tupla del fixture y se fortaleció con `assert extraer_concepto(frase) == concepto_esp` (ej. `"Fotocopias taller de sistemas"`). |
| `test_tabla_decision_alertas_hu06[R3]`: esperaba porcentaje acumulado `36.7%` usando `round(220000/600000*100, 1)` | **Corregida** | **Pregunta 1 (El esperado no salía de la regla):** El Escenario 1 de `HU-04` especifica textualmente *"una barra de progreso al 36.6%"* (truncamiento a 1 decimal, no redondeo hacia arriba). | Se fijó el esperado según el oráculo de `HU-04` (`36.6%` para el acumulado y `2.3%` para el gasto individual de `$14.000` sobre `$600.000`) con `pytest.approx(..., abs=0.05)`. |
| Filas extra en `test_extraer_monto_particiones_y_limites_validos`: `("10 lucas taxi", 10000)`, `("30 lucas mercado", 30000)` | **Descartada** | **Pregunta 3 (Redundante):** Pertenecen exactamente a la misma partición de equivalencia válida (entero positivo + `"lucas"` en minúsculas) ya cubierta por `("20 lucas de gasolina para la moto", 20000)`. | Se dejó un solo caso por partición de equivalencia y se priorizaron los pares de valores límite (`0` vs `1`, `-1` vs `1`, longitud `280` vs `281`). |
| `test_extraer_monto_invalidos`: `with pytest.raises(Exception):` sin patrón `match` | **Corregida** | **Pregunta 2 (Débil):** Capturar `Exception` sin verificar el mensaje permitiría que la prueba pasara si el código lanzara `TypeError` o un mensaje distinto al exigido por `HU-02` Escenario 2. | Se exigió `with pytest.raises(ValueError, match=r"^Monto ambiguo\. Por favor indique el valor en cifras numéricas$"):`. |
| `test_guardar_presupuesto_rechaza_tope_mayor_a_10_millones`: esperaba `ValueError` para `15000000` | **Descartada** | **Pregunta 1 (Regla inventada por la IA):** La historia `HU-05` solo exige que el presupuesto mensual sea *"un número positivo mayor a cero"*, sin definir ningún límite máximo superior. | Se descartó la restricción inventada y se probaron únicamente las particiones y bordes reales de `HU-05` (`0`, `-1`, `-50000`, `True`/`False` vs `1`, `600000`, `750000`). |

**Decisión:** Conservada, Corregida o Descartada.

---

## 3. Romper el código a propósito

Se introdujeron **4 errores intencionales (mutaciones manuales)** en el código fuente (`src/`), uno a la vez, ejecutando `pytest -v` tras cada cambio y revirtiéndolo inmediatamente con `git restore`:

| Cambio introducido | Archivo y línea | ¿Alguna prueba falló? | Qué hice |
|---|---|---|---|
| **M-01:** Cambiar `>` por `>=` en el umbral del 50% del presupuesto (`monto >= presupuesto * 0.5`) | `src/servicios.py:137` | **Sí**, falló `test_limites_umbral_50_y_sobregiro[0-repuesto moto 200000-True-False-None-200000-50.0]` | Nada: la prueba de valor límite en el borde exacto del `50.0%` (`$200.000` sobre `$400.000`) detectó el error de inmediato. Revertí con `git restore src/servicios.py`. |
| **M-02:** Cambiar `< 0` por `<= 0` en la condición de sobregiro (`(presupuesto - total_gastado) <= 0`) | `src/servicios.py:173` | **Sí**, falló `test_limites_umbral_50_y_sobregiro[320000-compra chaqueta 80000-True-False-None-0-20.0]` | Nada: la prueba de valor límite cuando el saldo restante queda exactamente en `$0` COP atrapó la falsa alerta de sobregiro. Revertí con `git restore src/servicios.py`. |
| **M-03:** Cambiar `FACTOR_MILES: int = 1000` por `100` | `src/parser_montos.py:14` | **Sí**, fallaron 12 pruebas (entre ellas `test_extraer_monto_particiones_y_limites_validos[20 lucas...-20000]` y `[1 LUCA-1000]`) | Nada: las aserciones de valor exacto (`20000` vs `2000`) protegieron el cálculo. Revertí con `git restore src/parser_montos.py`. |
| **M-04:** Desactivar la guarda `if PATRON_CUANTIFICADORES_AMBIGUOS.search(texto_normalizado):` reemplazándola por `if False:` | `src/parser_montos.py:49` | **No** inicialmente (`"gasté media luca en dulces"` seguía lanzando `ValueError` porque no tenía dígitos numéricos) | **Agregué el caso faltante** `"gasté 1 y media lucas en dulces"` en `test_extraer_monto_particiones_y_limites_invalidos` (cuando hay dígito `1` junto a la fracción `media`), verifiqué que con la mutación activa ahora **sí falla** (devolvía `1000` en vez de lanzar `ValueError`) y revertí `src/parser_montos.py` con `git restore`. |

---

## 4. Datos de prueba

**Origen:** Sintéticos generados con IA y curados manualmente en el fixture `@pytest.fixture(name="dataset_gastos_sinteticos_locales")` dentro de [`tests/test_reglas_negocio_s7.py`](file:///c:/Users/PIPE/OneDrive/Documentos/FinanzasPersonales-App/FinanzasPersonales-App/tests/test_reglas_negocio_s7.py). **Confirmo que no hay datos de personas reales** (se empleó el comercio ficticio `"Cafetería El Estudiante S.A.S. (Ficticia)"`, NIT ficticio `"900.000.000-1"` y teléfono ficticio `"300-000-0000"`).

**Casos difíciles incluidos:**
- **Tildes múltiples y puntuación:** `"alimentación: menú ejecutivo y café en cafetería 16.500"` (`16500`, `'Alimentación'`).
- **Letra `ñ` repetida y jerga local:** `"reparación por daño de piñón y cañería de freno moto 48 lucas"` (`48000`, `'Transporte/Moto'`).
- **Apóstrofo (`'`) en nombre comercial:** `"almuerzo en restaurante D'Luxe Bistró 22 mil"` (`22000`, `'Alimentación'`).
- **Espacios en blanco redundantes (inicio, medio y fin):** `"   fotocopias   taller   de   sistemas   4.500   "` (`4500`, `'Estudio'`, concepto normalizado a `"Fotocopias taller de sistemas"`).
- **Texto vacío y caracteres invisibles:** `""` y `"   \t  "` (verificados con `pytest.raises(ValueError)`).
- **Valores numéricos en cero (`0`):** `"bono navideño de promoción 0"`, `"descuento 0"`, `"0 lucas en parqueadero"` y presupuesto `0` (verificados como partición/borde inválido con `pytest.raises(ValueError)`).

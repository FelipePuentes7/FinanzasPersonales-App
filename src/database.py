"""Módulo de persistencia local en SQLite para FinanzasPersonales-App.

Implementa la creación del esquema y las operaciones CRUD sobre las tablas
`presupuesto`, `transacciones`, `ingresos_extra`, `gastos_fijos` y `creditos`
utilizando exclusivamente consultas SQL parametrizadas (`?`) para prevenir
inyección SQL (RNF-02 y RNF-03).
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Iterator

RUTA_DB_DEFECTO: Path = Path("data") / "finanzas.db"

MENSAJE_PRESUPUESTO_INVALIDO: str = (
    "El presupuesto mensual debe ser un número positivo mayor a cero"
)
MENSAJE_MONTO_TRANSACCION_INVALIDO: str = (
    "El monto de la transacción debe ser un entero positivo mayor a cero"
)
MENSAJE_CONCEPTO_INVALIDO: str = "El concepto del gasto no puede estar vacío"
MENSAJE_CATEGORIA_INVALIDA: str = "La categoría especificada no es válida"
MENSAJE_INGRESO_INVALIDO: str = (
    "El monto del ingreso extra debe ser un entero positivo mayor a cero"
)
MENSAJE_GASTO_FIJO_INVALIDO: str = (
    "El monto del gasto fijo debe ser un entero positivo mayor a cero"
)
MENSAJE_CREDITO_INVALIDO: str = (
    "Los datos del crédito deben tener valores enteros positivos válidos"
)
MENSAJE_CREDITO_SALDADO: str = (
    "Este crédito ya tiene todas sus cuotas pagadas"
)

CATEGORIAS_VALIDAS: tuple[str, ...] = (
    "Transporte/Moto",
    "Alimentación",
    "Estudio",
    "Ocio",
    "Gastos Varios",
)


@contextmanager
def obtener_conexion(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> Iterator[sqlite3.Connection]:
    """Abre y gestiona una conexión segura a la base de datos SQLite local.

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite local.

    Yields:
        Iterator[sqlite3.Connection]: Conexión activa a SQLite con `Row` factory.

    Raises:
        sqlite3.Error: Si ocurre un fallo de entrada/salida al abrir la base.
    """
    ruta = Path(ruta_db)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def inicializar_db(ruta_db: str | Path = RUTA_DB_DEFECTO) -> None:
    """Crea las 5 tablas del sistema si aún no existen en el archivo SQLite.

    Args:
        ruta_db (str | Path): Ruta hacia el archivo de base de datos SQLite.
    """
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS presupuesto (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                monto_mensual INTEGER NOT NULL CHECK (monto_mensual > 0),
                actualizado_en TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto INTEGER NOT NULL CHECK (monto > 0),
                categoria TEXT NOT NULL,
                es_ambiguo INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ingresos_extra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto INTEGER NOT NULL CHECK (monto > 0)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gastos_fijos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                monto INTEGER NOT NULL CHECK (monto > 0),
                categoria TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS creditos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                valor_cuota INTEGER NOT NULL CHECK (valor_cuota > 0),
                total_cuotas INTEGER NOT NULL CHECK (total_cuotas > 0),
                cuotas_pagadas INTEGER NOT NULL DEFAULT 0 CHECK (cuotas_pagadas >= 0),
                categoria TEXT NOT NULL
            )
            """
        )


def _es_entero_positivo(valor: Any) -> bool:
    """Verifica que un valor sea estrictamente `int` (no `bool`) y mayor a cero.

    Args:
        valor (Any): Valor por comprobar.

    Returns:
        bool: `True` si es un entero `> 0`; `False` en caso contrario.
    """
    return not isinstance(valor, bool) and isinstance(valor, int) and valor > 0


def guardar_presupuesto(
    monto_mensual: int,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Define o actualiza el tope de presupuesto mensual en SQLite (HU-05).

    Args:
        monto_mensual (int): Valor entero positivo en pesos colombianos (COP).
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: El monto mensual almacenado exitosamente.

    Raises:
        ValueError: Si `monto_mensual` no es un entero o es menor o igual a cero.
    """
    if not _es_entero_positivo(monto_mensual):
        raise ValueError(MENSAJE_PRESUPUESTO_INVALIDO)

    inicializar_db(ruta_db)
    marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with obtener_conexion(ruta_db) as conn:
        conn.execute(
            """
            INSERT INTO presupuesto (id, monto_mensual, actualizado_en)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                monto_mensual = excluded.monto_mensual,
                actualizado_en = excluded.actualizado_en
            """,
            (monto_mensual, marca_tiempo),
        )

    return monto_mensual


def obtener_presupuesto(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int | None:
    """Consulta el presupuesto mensual activo almacenado en SQLite (HU-04).

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int | None: Monto del presupuesto mensual en COP, o `None` si aún
            no ha sido configurado por el usuario.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            "SELECT monto_mensual FROM presupuesto WHERE id = 1"
        ).fetchone()

    if fila is None:
        return None
    return int(fila["monto_mensual"])


def _validar_datos_transaccion(
    concepto: str,
    monto: int,
    categoria: str,
) -> str:
    """Valida los campos de una transacción antes de insertarla en SQLite.

    Args:
        concepto (str): Descripción corta del gasto.
        monto (int): Valor entero positivo en COP.
        categoria (str): Categoría asignada dentro de `CATEGORIAS_VALIDAS`.

    Returns:
        str: Concepto limpio sin espacios extremos.

    Raises:
        ValueError: Si el concepto está vacío, el monto no es positivo o la
            categoría no pertenece al catálogo fijo del sistema.
    """
    if not isinstance(concepto, str) or not concepto.strip():
        raise ValueError(MENSAJE_CONCEPTO_INVALIDO)

    if not _es_entero_positivo(monto):
        raise ValueError(MENSAJE_MONTO_TRANSACCION_INVALIDO)

    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    return concepto.strip()


def insertar_transaccion(  # pylint: disable=too-many-arguments
    concepto: str,
    monto: int,
    categoria: str,
    *,
    fecha: str | None = None,
    es_ambiguo: bool = False,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Almacena una nueva transacción de gasto de forma parametrizada (HU-01).

    Args:
        concepto (str): Descripción limpia del gasto (ej. 'Almuerzo corriente').
        monto (int): Valor entero positivo en COP.
        categoria (str): Categoría asignada dentro de `CATEGORIAS_VALIDAS`.
        fecha (str | None): Fecha en formato 'YYYY-MM-DD'.
        es_ambiguo (bool): Marca para conceptos clasificados por defecto (HU-03).
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Identificador único (`id`) de la transacción insertada.
    """
    concepto_limpio = _validar_datos_transaccion(concepto, monto, categoria)
    fecha_registro = fecha or datetime.now().strftime("%Y-%m-%d")
    bandera_ambiguo = 1 if es_ambiguo else 0

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transacciones (fecha, concepto, monto, categoria, es_ambiguo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (fecha_registro, concepto_limpio, monto, categoria, bandera_ambiguo),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_transacciones(
    categoria: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> list[dict[str, Any]]:
    """Consulta el historial de transacciones con filtro opcional por categoría.

    Args:
        categoria (str | None): Categoría a filtrar (`None`, `""` o `"Todas"`).
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        list[dict[str, Any]]: Lista de transacciones ordenadas por `id DESC`.

    Raises:
        ValueError: Si se especifica una categoría fuera de `CATEGORIAS_VALIDAS`.
    """
    inicializar_db(ruta_db)
    filtro = categoria.strip() if isinstance(categoria, str) else ""

    with obtener_conexion(ruta_db) as conn:
        if filtro and filtro != "Todas":
            if filtro not in CATEGORIAS_VALIDAS:
                raise ValueError(MENSAJE_CATEGORIA_INVALIDA)
            filas = conn.execute(
                """
                SELECT id, fecha, concepto, monto, categoria, es_ambiguo
                FROM transacciones
                WHERE categoria = ?
                ORDER BY id DESC
                """,
                (filtro,),
            ).fetchall()
        else:
            filas = conn.execute(
                """
                SELECT id, fecha, concepto, monto, categoria, es_ambiguo
                FROM transacciones
                ORDER BY id DESC
                """
            ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "fecha": str(fila["fecha"]),
            "concepto": str(fila["concepto"]),
            "monto": int(fila["monto"]),
            "categoria": str(fila["categoria"]),
            "es_ambiguo": bool(fila["es_ambiguo"]),
        }
        for fila in filas
    ]


def actualizar_categoria_transaccion(
    transaccion_id: int,
    nueva_categoria: str,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> bool:
    """Actualiza la categoría de una transacción y limpia su marca de ambigüedad.

    Args:
        transaccion_id (int): Identificador de la transacción por modificar.
        nueva_categoria (str): Nueva categoría válida seleccionada por el usuario.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        bool: `True` si el registro existía y fue actualizado; `False` si no existe.

    Raises:
        ValueError: Si `nueva_categoria` no pertenece a `CATEGORIAS_VALIDAS`.
    """
    if nueva_categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            UPDATE transacciones
            SET categoria = ?, es_ambiguo = 0
            WHERE id = ?
            """,
            (nueva_categoria, transaccion_id),
        )
        actualizado = cursor.rowcount > 0

    return actualizado


def insertar_ingreso_extra(
    concepto: str,
    monto: int,
    *,
    fecha: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra un ingreso extra o abono de forma parametrizada (HU-09).

    Args:
        concepto (str): Origen o descripción del ingreso extra.
        monto (int): Valor entero positivo en COP.
        fecha (str | None): Fecha en formato 'YYYY-MM-DD'.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Identificador (`id`) del ingreso extra registrado.

    Raises:
        ValueError: Si el concepto está vacío o el monto no es un entero `> 0`.
    """
    if not isinstance(concepto, str) or not concepto.strip():
        raise ValueError(MENSAJE_CONCEPTO_INVALIDO)
    if not _es_entero_positivo(monto):
        raise ValueError(MENSAJE_INGRESO_INVALIDO)

    fecha_registro = fecha or datetime.now().strftime("%Y-%m-%d")
    inicializar_db(ruta_db)

    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO ingresos_extra (fecha, concepto, monto)
            VALUES (?, ?, ?)
            """,
            (fecha_registro, concepto.strip(), monto),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_ingresos_extra(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> list[dict[str, Any]]:
    """Lista todos los ingresos extra registrados en el periodo (HU-09).

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        list[dict[str, Any]]: Lista de ingresos con `id`, `fecha`, `concepto`, `monto`.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, fecha, concepto, monto
            FROM ingresos_extra
            ORDER BY id DESC
            """
        ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "fecha": str(fila["fecha"]),
            "concepto": str(fila["concepto"]),
            "monto": int(fila["monto"]),
        }
        for fila in filas
    ]


def crear_gasto_fijo(
    nombre: str,
    monto: int,
    categoria: str = "Gastos Varios",
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra una plantilla de gasto fijo mensual recurrente (HU-10).

    Args:
        nombre (str): Nombre del compromiso fijo (ej. 'Arriendo', 'Internet').
        monto (int): Valor mensual entero positivo en COP.
        categoria (str): Categoría asociada dentro de `CATEGORIAS_VALIDAS`.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Identificador (`id`) del gasto fijo creado.

    Raises:
        ValueError: Si el nombre está vacío, el monto es `<= 0` o la categoría
            es inválida.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError(MENSAJE_CONCEPTO_INVALIDO)
    if not _es_entero_positivo(monto):
        raise ValueError(MENSAJE_GASTO_FIJO_INVALIDO)
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO gastos_fijos (nombre, monto, categoria, activo)
            VALUES (?, ?, ?, 1)
            """,
            (nombre.strip(), monto, categoria),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_gastos_fijos(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> list[dict[str, Any]]:
    """Consulta todos los gastos fijos mensuales activos (HU-10).

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        list[dict[str, Any]]: Lista de gastos fijos con `id`, `nombre`, `monto`
            y `categoria`.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, nombre, monto, categoria, activo
            FROM gastos_fijos
            WHERE activo = 1
            ORDER BY id ASC
            """
        ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "nombre": str(fila["nombre"]),
            "monto": int(fila["monto"]),
            "categoria": str(fila["categoria"]),
            "activo": bool(fila["activo"]),
        }
        for fila in filas
    ]


def eliminar_gasto_fijo(
    gasto_fijo_id: int,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> bool:
    """Elimina un gasto fijo mensual de la plantilla recurrente (HU-10).

    Args:
        gasto_fijo_id (int): Identificador del gasto fijo por eliminar.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        bool: `True` si se eliminó el registro; `False` si no existía.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            "DELETE FROM gastos_fijos WHERE id = ?",
            (gasto_fijo_id,),
        )
        return cursor.rowcount > 0


def crear_credito(  # pylint: disable=too-many-arguments
    nombre: str,
    valor_cuota: int,
    total_cuotas: int,
    *,
    cuotas_pagadas: int = 0,
    categoria: str = "Gastos Varios",
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra una obligación o crédito diferido a cuotas mensuales (HU-11).

    Args:
        nombre (str): Nombre del crédito (ej. 'Cuota Moto', 'Tarjeta Crédito').
        valor_cuota (int): Valor entero positivo de cada cuota mensual en COP.
        total_cuotas (int): Número total de cuotas pactadas (`> 0`).
        cuotas_pagadas (int): Cuotas pagadas inicialmente (`0 <= pagadas <= total`).
        categoria (str): Categoría del gasto cuando se paga una cuota.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Identificador (`id`) del crédito creado.

    Raises:
        ValueError: Si los parámetros numéricos o de texto son inválidos.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError(MENSAJE_CONCEPTO_INVALIDO)
    if not _es_entero_positivo(valor_cuota) or not _es_entero_positivo(total_cuotas):
        raise ValueError(MENSAJE_CREDITO_INVALIDO)
    if (
        isinstance(cuotas_pagadas, bool)
        or not isinstance(cuotas_pagadas, int)
        or cuotas_pagadas < 0
        or cuotas_pagadas > total_cuotas
    ):
        raise ValueError(MENSAJE_CREDITO_INVALIDO)
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO creditos (
                nombre, valor_cuota, total_cuotas, cuotas_pagadas, categoria
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (nombre.strip(), valor_cuota, total_cuotas, cuotas_pagadas, categoria),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_creditos(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> list[dict[str, Any]]:
    """Consulta todos los créditos registrados con sus métricas de avance (HU-11).

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        list[dict[str, Any]]: Lista de créditos con cuotas restantes, saldo
            pendiente estimado y porcentaje de progreso.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, nombre, valor_cuota, total_cuotas, cuotas_pagadas, categoria
            FROM creditos
            ORDER BY id ASC
            """
        ).fetchall()

    resultado: list[dict[str, Any]] = []
    for fila in filas:
        valor_cuota = int(fila["valor_cuota"])
        total = int(fila["total_cuotas"])
        pagadas = int(fila["cuotas_pagadas"])
        restantes = max(total - pagadas, 0)
        porcentaje = int((pagadas / total) * 1000) / 10.0 if total > 0 else 0.0
        resultado.append(
            {
                "id": int(fila["id"]),
                "nombre": str(fila["nombre"]),
                "valor_cuota": valor_cuota,
                "total_cuotas": total,
                "cuotas_pagadas": pagadas,
                "cuotas_restantes": restantes,
                "saldo_pendiente": restantes * valor_cuota,
                "porcentaje_pagado": porcentaje,
                "pagado_completo": pagadas >= total,
                "categoria": str(fila["categoria"]),
            }
        )
    return resultado


def incrementar_cuota_credito(
    credito_id: int,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Avanza en +1 el contador de cuotas pagadas de un crédito activo (HU-11).

    Args:
        credito_id (int): Identificador del crédito.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        dict[str, Any]: Datos actualizados del crédito tras registrar la cuota.

    Raises:
        ValueError: Si el crédito no existe o si ya tiene todas sus cuotas pagadas.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            """
            SELECT id, nombre, valor_cuota, total_cuotas, cuotas_pagadas, categoria
            FROM creditos
            WHERE id = ?
            """,
            (credito_id,),
        ).fetchone()

        if fila is None:
            raise ValueError("El crédito especificado no existe")

        pagadas = int(fila["cuotas_pagadas"])
        total = int(fila["total_cuotas"])
        if pagadas >= total:
            raise ValueError(MENSAJE_CREDITO_SALDADO)

        nueva_cuota = pagadas + 1
        conn.execute(
            "UPDATE creditos SET cuotas_pagadas = ? WHERE id = ?",
            (nueva_cuota, credito_id),
        )

    creditos_actualizados = listar_creditos(ruta_db=ruta_db)
    for item in creditos_actualizados:
        if item["id"] == credito_id:
            return item
    raise ValueError("El crédito especificado no existe")

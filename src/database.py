"""Módulo de persistencia local en SQLite para FinanzasPersonales-App.

Implementa la creación del esquema y las operaciones CRUD sobre las tablas
`presupuesto` y `transacciones` utilizando exclusivamente consultas SQL
parametrizadas (`?`) para prevenir inyección SQL (RNF-02 y RNF-03).
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
MENSAJE_CONCEPTO_INVALIDO: str = (
    "El concepto del gasto no puede estar vacío"
)
MENSAJE_CATEGORIA_INVALIDA: str = "La categoría especificada no es válida"

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

    Crea automáticamente el directorio padre si no existe, configura
    `sqlite3.Row` para acceso por nombre de columna y garantiza el `commit`
    o cierre limpio de la conexión al salir del bloque contextual.

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
    """Crea las tablas `presupuesto` y `transacciones` si aún no existen.

    Args:
        ruta_db (str | Path): Ruta hacia el archivo de base de datos SQLite.

    Returns:
        None

    Raises:
        sqlite3.Error: Si ocurre un error al ejecutar las sentencias DDL.
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
    if (
        isinstance(monto_mensual, bool)
        or not isinstance(monto_mensual, int)
        or monto_mensual <= 0
    ):
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

    Raises:
        sqlite3.Error: Si ocurre un error de lectura en la base de datos.
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

    if isinstance(monto, bool) or not isinstance(monto, int) or monto <= 0:
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
        fecha (str | None): Fecha en formato 'YYYY-MM-DD'. Si es `None`, usa la
            fecha local actual.
        es_ambiguo (bool): Indica si el concepto fue clasificado temporalmente
            en 'Gastos Varios' por falta de contexto semántico (HU-03 Esc. 2).
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Identificador único (`id`) de la transacción insertada.

    Raises:
        ValueError: Si el concepto está vacío, el monto es `<= 0` o la categoría
            no es válida.
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
        categoria (str | None): Categoría a filtrar. Si es `None`, `""` o `"Todas"`,
            retorna todas las transacciones registradas.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        list[dict[str, Any]]: Lista de transacciones ordenadas de la más reciente
            a la más antigua (`id`, `fecha`, `concepto`, `monto`, `categoria`,
            `es_ambiguo`).

    Raises:
        ValueError: Si se especifica una categoría de filtro que no existe en
            `CATEGORIAS_VALIDAS`.
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

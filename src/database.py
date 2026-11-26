"""Módulo de persistencia local en SQLite para FinanzasPersonales-App.

Implementa la creación del esquema multiusuario y por periodos mensuales (`YYYY-MM`),
así como las operaciones CRUD sobre las tablas `usuarios`, `presupuesto`,
`periodos_mensuales`, `transacciones`, `ingresos_extra`, `gastos_fijos` y
`creditos` utilizando exclusivamente consultas SQL parametrizadas (`?`).
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
MENSAJE_META_AHORRO_INVALIDA: str = (
    "La meta de ahorro debe ser un número entero mayor o igual a cero"
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


def obtener_periodo_actual() -> str:
    """Retorna el periodo mensual actual en formato `'YYYY-MM'`.

    Returns:
        str: Periodo actual (ej. `'2026-11'`).
    """
    return datetime.now().strftime("%Y-%m")


@contextmanager
def obtener_conexion(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> Iterator[sqlite3.Connection]:
    """Abre y gestiona una conexión segura a la base de datos SQLite local.

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite local.

    Yields:
        Iterator[sqlite3.Connection]: Conexión activa a SQLite con `Row` factory.
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


def _asegurar_columnas_migracion(cursor: sqlite3.Cursor) -> None:
    """Agrega columnas de `usuario_id` y `periodo` en bases existentes si faltan."""
    migraciones = (
        ("transacciones", "usuario_id", "INTEGER NOT NULL DEFAULT 1"),
        ("transacciones", "periodo", "TEXT NOT NULL DEFAULT '2026-11'"),
        ("ingresos_extra", "usuario_id", "INTEGER NOT NULL DEFAULT 1"),
        ("ingresos_extra", "periodo", "TEXT NOT NULL DEFAULT '2026-11'"),
        ("gastos_fijos", "usuario_id", "INTEGER NOT NULL DEFAULT 1"),
        ("creditos", "usuario_id", "INTEGER NOT NULL DEFAULT 1"),
    )
    tablas_permitidas = {
        "transacciones",
        "ingresos_extra",
        "gastos_fijos",
        "creditos",
    }
    for tabla, columna, definicion in migraciones:
        if tabla not in tablas_permitidas:
            continue
        filas_info = cursor.execute(f"PRAGMA table_info({tabla})").fetchall()
        nombres_col = {str(fila["name"]) for fila in filas_info}
        if columna not in nombres_col:
            cursor.execute(
                f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}"
            )


def inicializar_db(ruta_db: str | Path = RUTA_DB_DEFECTO) -> None:
    """Crea las tablas del esquema multiusuario y mensual si aún no existen.

    Args:
        ruta_db (str | Path): Ruta hacia el archivo de base de datos SQLite.
    """
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT NOT NULL
            )
            """
        )
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
            CREATE TABLE IF NOT EXISTS periodos_mensuales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL DEFAULT 1,
                periodo TEXT NOT NULL,
                presupuesto_base INTEGER NOT NULL CHECK (presupuesto_base > 0),
                meta_ahorro INTEGER NOT NULL DEFAULT 0 CHECK (meta_ahorro >= 0),
                saldo_arrastrado INTEGER NOT NULL DEFAULT 0,
                cerrado INTEGER NOT NULL DEFAULT 0,
                actualizado_en TEXT NOT NULL,
                UNIQUE(usuario_id, periodo)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL DEFAULT 1,
                periodo TEXT NOT NULL DEFAULT '2026-11',
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
                usuario_id INTEGER NOT NULL DEFAULT 1,
                periodo TEXT NOT NULL DEFAULT '2026-11',
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
                usuario_id INTEGER NOT NULL DEFAULT 1,
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
                usuario_id INTEGER NOT NULL DEFAULT 1,
                nombre TEXT NOT NULL,
                valor_cuota INTEGER NOT NULL CHECK (valor_cuota > 0),
                total_cuotas INTEGER NOT NULL CHECK (total_cuotas > 0),
                cuotas_pagadas INTEGER NOT NULL DEFAULT 0 CHECK (cuotas_pagadas >= 0),
                categoria TEXT NOT NULL
            )
            """
        )
        _asegurar_columnas_migracion(cursor)


def _es_entero_positivo(valor: Any) -> bool:
    """Verifica que un valor sea estrictamente `int` (no `bool`) y mayor a cero."""
    return not isinstance(valor, bool) and isinstance(valor, int) and valor > 0


def _es_entero_no_negativo(valor: Any) -> bool:
    """Verifica que un valor sea estrictamente `int` (no `bool`) y `>= 0`."""
    return not isinstance(valor, bool) and isinstance(valor, int) and valor >= 0


def guardar_presupuesto(  # pylint: disable=too-many-arguments
    monto_mensual: int,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
    meta_ahorro: int | None = None,
    saldo_arrastrado: int | None = None,
) -> int:
    """Define o actualiza el tope de presupuesto mensual por usuario y periodo.

    Args:
        monto_mensual (int): Valor entero positivo en pesos colombianos (COP).
        ruta_db (str | Path): Ruta del archivo SQLite.
        usuario_id (int): Identificador del usuario propietario.
        periodo (str | None): Periodo `'YYYY-MM'` (por defecto el mes actual).
        meta_ahorro (int | None): Meta de ahorro opcional del mes (`>= 0`).
        saldo_arrastrado (int | None): Saldo arrastrado del mes anterior.

    Returns:
        int: El monto mensual almacenado exitosamente.

    Raises:
        ValueError: Si `monto_mensual` no es un entero o es menor o igual a cero.
    """
    if not _es_entero_positivo(monto_mensual):
        raise ValueError(MENSAJE_PRESUPUESTO_INVALIDO)

    if meta_ahorro is not None and not _es_entero_no_negativo(meta_ahorro):
        raise ValueError(MENSAJE_META_AHORRO_INVALIDA)

    periodo_activo = (periodo or obtener_periodo_actual()).strip()
    inicializar_db(ruta_db)
    marca_tiempo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with obtener_conexion(ruta_db) as conn:
        if usuario_id == 1:
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

        actual = conn.execute(
            """
            SELECT meta_ahorro, saldo_arrastrado
            FROM periodos_mensuales
            WHERE usuario_id = ? AND periodo = ?
            """,
            (usuario_id, periodo_activo),
        ).fetchone()

        ahorro_final = (
            meta_ahorro
            if meta_ahorro is not None
            else (int(actual["meta_ahorro"]) if actual is not None else 0)
        )
        arrastre_final = (
            saldo_arrastrado
            if saldo_arrastrado is not None
            else (int(actual["saldo_arrastrado"]) if actual is not None else 0)
        )

        conn.execute(
            """
            INSERT INTO periodos_mensuales (
                usuario_id, periodo, presupuesto_base, meta_ahorro,
                saldo_arrastrado, cerrado, actualizado_en
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(usuario_id, periodo) DO UPDATE SET
                presupuesto_base = excluded.presupuesto_base,
                meta_ahorro = excluded.meta_ahorro,
                saldo_arrastrado = excluded.saldo_arrastrado,
                actualizado_en = excluded.actualizado_en
            """,
            (
                usuario_id,
                periodo_activo,
                monto_mensual,
                ahorro_final,
                arrastre_final,
                marca_tiempo,
            ),
        )

    return monto_mensual


def obtener_presupuesto(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
) -> int | None:
    """Consulta el presupuesto mensual activo del usuario en el periodo indicado.

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.
        usuario_id (int): Identificador del usuario.
        periodo (str | None): Periodo `'YYYY-MM'`.

    Returns:
        int | None: Monto del presupuesto mensual en COP, o `None`.
    """
    periodo_activo = (periodo or obtener_periodo_actual()).strip()
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila_periodo = conn.execute(
            """
            SELECT presupuesto_base
            FROM periodos_mensuales
            WHERE usuario_id = ? AND periodo = ?
            """,
            (usuario_id, periodo_activo),
        ).fetchone()

        if fila_periodo is not None:
            return int(fila_periodo["presupuesto_base"])

        if usuario_id == 1 and periodo is None:
            fila_legacy = conn.execute(
                "SELECT monto_mensual FROM presupuesto WHERE id = 1"
            ).fetchone()
            if fila_legacy is not None:
                return int(fila_legacy["monto_mensual"])

    return None


def obtener_datos_periodo(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
) -> dict[str, Any]:
    """Obtiene la configuración completa de un periodo mensual para un usuario.

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite.
        usuario_id (int): Identificador del usuario.
        periodo (str | None): Periodo `'YYYY-MM'`.

    Returns:
        dict[str, Any]: Diccionario con `periodo`, `presupuesto_base`,
            `meta_ahorro`, `saldo_arrastrado` y `cerrado`.
    """
    periodo_activo = (periodo or obtener_periodo_actual()).strip()
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            """
            SELECT presupuesto_base, meta_ahorro, saldo_arrastrado, cerrado
            FROM periodos_mensuales
            WHERE usuario_id = ? AND periodo = ?
            """,
            (usuario_id, periodo_activo),
        ).fetchone()

    if fila is not None:
        return {
            "periodo": periodo_activo,
            "presupuesto_base": int(fila["presupuesto_base"]),
            "meta_ahorro": int(fila["meta_ahorro"]),
            "saldo_arrastrado": int(fila["saldo_arrastrado"]),
            "cerrado": bool(fila["cerrado"]),
        }

    presupuesto_fallback = obtener_presupuesto(
        ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    return {
        "periodo": periodo_activo,
        "presupuesto_base": presupuesto_fallback,
        "meta_ahorro": 0,
        "saldo_arrastrado": 0,
        "cerrado": False,
    }


def guardar_meta_ahorro(
    meta_ahorro: int,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Actualiza la meta de ahorro mensual de un usuario en el periodo activo.

    Args:
        meta_ahorro (int): Monto entero mayor o igual a cero en COP.
        usuario_id (int): Identificador del usuario.
        periodo (str | None): Periodo `'YYYY-MM'`.
        ruta_db (str | Path): Ruta del archivo SQLite.

    Returns:
        int: Valor de la meta de ahorro almacenada.

    Raises:
        ValueError: Si `meta_ahorro < 0` o no hay presupuesto base configurado.
    """
    if not _es_entero_no_negativo(meta_ahorro):
        raise ValueError(MENSAJE_META_AHORRO_INVALIDA)

    datos = obtener_datos_periodo(
        ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
    )
    if datos["presupuesto_base"] is None:
        raise ValueError("Configure primero el presupuesto mensual del periodo")

    guardar_presupuesto(
        int(datos["presupuesto_base"]),
        ruta_db,
        usuario_id=usuario_id,
        periodo=datos["periodo"],
        meta_ahorro=meta_ahorro,
        saldo_arrastrado=int(datos["saldo_arrastrado"]),
    )
    return meta_ahorro


def marcar_periodo_cerrado(
    *,
    usuario_id: int = 1,
    periodo: str,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> None:
    """Marca un periodo mensual como cerrado tras arrastrar su saldo."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        conn.execute(
            """
            UPDATE periodos_mensuales
            SET cerrado = 1
            WHERE usuario_id = ? AND periodo = ?
            """,
            (usuario_id, periodo.strip()),
        )


def _validar_datos_transaccion(
    concepto: str,
    monto: int,
    categoria: str,
) -> str:
    """Valida los campos de una transacción antes de insertarla en SQLite."""
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
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Almacena una nueva transacción de gasto aislada por usuario y periodo."""
    concepto_limpio = _validar_datos_transaccion(concepto, monto, categoria)
    fecha_registro = fecha or datetime.now().strftime("%Y-%m-%d")
    periodo_activo = (periodo or fecha_registro[:7]).strip()
    bandera_ambiguo = 1 if es_ambiguo else 0

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transacciones (
                usuario_id, periodo, fecha, concepto, monto, categoria, es_ambiguo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                periodo_activo,
                fecha_registro,
                concepto_limpio,
                monto,
                categoria,
                bandera_ambiguo,
            ),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_transacciones(
    categoria: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
    busqueda: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta el historial de transacciones del usuario con filtros opcionales."""
    inicializar_db(ruta_db)
    filtro_cat = categoria.strip() if isinstance(categoria, str) else ""
    if filtro_cat == "Todas":
        filtro_cat = ""
    if filtro_cat and filtro_cat not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    filtro_periodo = periodo.strip() if isinstance(periodo, str) else ""
    filtro_busq = busqueda.strip().lower() if isinstance(busqueda, str) else ""
    patron_like = f"%{filtro_busq}%" if filtro_busq else ""

    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, usuario_id, periodo, fecha, concepto, monto,
                   categoria, es_ambiguo
            FROM transacciones
            WHERE usuario_id = ?
              AND (? = '' OR periodo = ?)
              AND (? = '' OR categoria = ?)
              AND (? = '' OR LOWER(concepto) LIKE ?)
            ORDER BY id DESC
            """,
            (
                usuario_id,
                filtro_periodo,
                filtro_periodo,
                filtro_cat,
                filtro_cat,
                filtro_busq,
                patron_like,
            ),
        ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "usuario_id": int(fila["usuario_id"]),
            "periodo": str(fila["periodo"]),
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
    *,
    usuario_id: int = 1,
) -> bool:
    """Actualiza la categoría de una transacción verificando pertenencia al usuario."""
    if nueva_categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(MENSAJE_CATEGORIA_INVALIDA)

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            UPDATE transacciones
            SET categoria = ?, es_ambiguo = 0
            WHERE id = ? AND usuario_id = ?
            """,
            (nueva_categoria, transaccion_id, usuario_id),
        )
        return cursor.rowcount > 0


def insertar_ingreso_extra(  # pylint: disable=too-many-arguments
    concepto: str,
    monto: int,
    *,
    fecha: str | None = None,
    usuario_id: int = 1,
    periodo: str | None = None,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra un ingreso extra o abono aislado por usuario y periodo (HU-09)."""
    if not isinstance(concepto, str) or not concepto.strip():
        raise ValueError(MENSAJE_CONCEPTO_INVALIDO)
    if not _es_entero_positivo(monto):
        raise ValueError(MENSAJE_INGRESO_INVALIDO)

    fecha_registro = fecha or datetime.now().strftime("%Y-%m-%d")
    periodo_activo = (periodo or fecha_registro[:7]).strip()
    inicializar_db(ruta_db)

    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            """
            INSERT INTO ingresos_extra (usuario_id, periodo, fecha, concepto, monto)
            VALUES (?, ?, ?, ?, ?)
            """,
            (usuario_id, periodo_activo, fecha_registro, concepto.strip(), monto),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_ingresos_extra(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    periodo: str | None = None,
) -> list[dict[str, Any]]:
    """Lista los ingresos extra registrados por un usuario en el periodo."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        if periodo is not None and periodo.strip():
            filas = conn.execute(
                """
                SELECT id, usuario_id, periodo, fecha, concepto, monto
                FROM ingresos_extra
                WHERE usuario_id = ? AND periodo = ?
                ORDER BY id DESC
                """,
                (usuario_id, periodo.strip()),
            ).fetchall()
        else:
            filas = conn.execute(
                """
                SELECT id, usuario_id, periodo, fecha, concepto, monto
                FROM ingresos_extra
                WHERE usuario_id = ?
                ORDER BY id DESC
                """,
                (usuario_id,),
            ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "usuario_id": int(fila["usuario_id"]),
            "periodo": str(fila["periodo"]),
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
    usuario_id: int = 1,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra una plantilla de gasto fijo mensual para un usuario (HU-10)."""
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
            INSERT INTO gastos_fijos (usuario_id, nombre, monto, categoria, activo)
            VALUES (?, ?, ?, ?, 1)
            """,
            (usuario_id, nombre.strip(), monto, categoria),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_gastos_fijos(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
) -> list[dict[str, Any]]:
    """Consulta los gastos fijos activos pertenecientes al usuario indicado."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, usuario_id, nombre, monto, categoria, activo
            FROM gastos_fijos
            WHERE usuario_id = ? AND activo = 1
            ORDER BY id ASC
            """,
            (usuario_id,),
        ).fetchall()

    return [
        {
            "id": int(fila["id"]),
            "usuario_id": int(fila["usuario_id"]),
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
    *,
    usuario_id: int = 1,
) -> bool:
    """Elimina un gasto fijo verificando que pertenezca al usuario autenticado."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        cursor = conn.execute(
            "DELETE FROM gastos_fijos WHERE id = ? AND usuario_id = ?",
            (gasto_fijo_id, usuario_id),
        )
        return cursor.rowcount > 0


def crear_credito(  # pylint: disable=too-many-arguments
    nombre: str,
    valor_cuota: int,
    total_cuotas: int,
    *,
    cuotas_pagadas: int = 0,
    categoria: str = "Gastos Varios",
    usuario_id: int = 1,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> int:
    """Registra una obligación a cuotas asociada al usuario indicado (HU-11)."""
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
                usuario_id, nombre, valor_cuota, total_cuotas,
                cuotas_pagadas, categoria
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                usuario_id,
                nombre.strip(),
                valor_cuota,
                total_cuotas,
                cuotas_pagadas,
                categoria,
            ),
        )
        nuevo_id = cursor.lastrowid

    return int(nuevo_id or 0)


def listar_creditos(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
) -> list[dict[str, Any]]:
    """Consulta todos los créditos del usuario con sus métricas de avance."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        filas = conn.execute(
            """
            SELECT id, usuario_id, nombre, valor_cuota, total_cuotas,
                   cuotas_pagadas, categoria
            FROM creditos
            WHERE usuario_id = ?
            ORDER BY id ASC
            """,
            (usuario_id,),
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
                "usuario_id": int(fila["usuario_id"]),
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
    *,
    usuario_id: int = 1,
) -> dict[str, Any]:
    """Avanza en +1 las cuotas pagadas verificando propiedad del usuario (HU-11)."""
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            """
            SELECT id, nombre, valor_cuota, total_cuotas, cuotas_pagadas, categoria
            FROM creditos
            WHERE id = ? AND usuario_id = ?
            """,
            (credito_id, usuario_id),
        ).fetchone()

        if fila is None:
            raise ValueError("El crédito especificado no existe")

        pagadas = int(fila["cuotas_pagadas"])
        total = int(fila["total_cuotas"])
        if pagadas >= total:
            raise ValueError(MENSAJE_CREDITO_SALDADO)

        nueva_cuota = pagadas + 1
        conn.execute(
            "UPDATE creditos SET cuotas_pagadas = ? WHERE id = ? AND usuario_id = ?",
            (nueva_cuota, credito_id, usuario_id),
        )

    creditos_actualizados = listar_creditos(ruta_db=ruta_db, usuario_id=usuario_id)
    for item in creditos_actualizados:
        if item["id"] == credito_id:
            return item
    raise ValueError("El crédito especificado no existe")

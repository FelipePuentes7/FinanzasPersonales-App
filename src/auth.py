"""Módulo de autenticación segura y gestión de sesiones multiusuario (HU-12).

Implementa el hash criptográfico de contraseñas mediante `hashlib.scrypt`
con sal aleatoria de 16 bytes (`secrets.token_hex`), verificación en tiempo
constante (`hmac.compare_digest`) y registro/autenticación de usuarios en
SQLite con consultas 100% parametrizadas (`?`).
"""

from datetime import datetime
import hashlib
import hmac
from pathlib import Path
import re
import secrets
from typing import Any

from src.database import RUTA_DB_DEFECTO, inicializar_db, obtener_conexion

LONGITUD_MINIMA_CLAVE: int = 6
SCRYPT_N: int = 16384
SCRYPT_R: int = 8
SCRYPT_P: int = 1
SCRYPT_DKLEN: int = 32

MENSAJE_NOMBRE_USUARIO_INVALIDO: str = (
    "El nombre del usuario no puede estar vacío"
)
MENSAJE_EMAIL_INVALIDO: str = (
    "Ingrese un correo electrónico válido"
)
MENSAJE_CLAVE_CORTA: str = (
    "La contraseña debe tener al menos 6 caracteres"
)
MENSAJE_EMAIL_DUPLICADO: str = (
    "Ya existe una cuenta registrada con ese correo electrónico"
)
MENSAJE_CREDENCIALES_INVALIDAS: str = (
    "Credenciales inválidas. Verifique su correo y contraseña"
)

PATRON_EMAIL_BASICO: re.Pattern[str] = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


def generate_password_hash(password: str) -> str:
    """Genera un hash seguro de contraseña con `scrypt` y sal criptográfica.

    Args:
        password (str): Contraseña en texto plano (`>= 6` caracteres).

    Returns:
        str: Hash codificado con formato `'scrypt$16384$8$1$<sal>$<hash>'`.

    Raises:
        ValueError: Si la contraseña no es una cadena o tiene menos de 6 caracteres.
    """
    if (
        not isinstance(password, str)
        or len(password.strip()) < LONGITUD_MINIMA_CLAVE
    ):
        raise ValueError(MENSAJE_CLAVE_CORTA)

    sal_hex = secrets.token_hex(16)
    clave_derivada = hashlib.scrypt(
        password.encode("utf-8"),
        salt=sal_hex.encode("utf-8"),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${sal_hex}${clave_derivada.hex()}"


def check_password_hash(password_hash: str, password: str) -> bool:
    """Verifica una contraseña contra su hash `scrypt` en tiempo constante.

    Args:
        password_hash (str): Hash almacenado en la base de datos.
        password (str): Contraseña candidata en texto plano.

    Returns:
        bool: `True` si la contraseña coincide; `False` en caso contrario.
    """
    if not isinstance(password_hash, str) or not isinstance(password, str):
        return False

    partes = password_hash.split("$")
    if len(partes) != 6 or partes[0] != "scrypt":
        return False

    try:
        param_n = int(partes[1])
        param_r = int(partes[2])
        param_p = int(partes[3])
        sal_hex = partes[4]
        hash_esperado = partes[5]
    except ValueError:
        return False

    clave_candidata = hashlib.scrypt(
        password.encode("utf-8"),
        salt=sal_hex.encode("utf-8"),
        n=param_n,
        r=param_r,
        p=param_p,
        dklen=SCRYPT_DKLEN,
    )
    return hmac.compare_digest(clave_candidata.hex(), hash_esperado)


def registrar_usuario(
    nombre: str,
    email: str,
    password: str,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Registra un nuevo usuario con contraseña hasheada mediante `scrypt` (HU-12).

    Args:
        nombre (str): Nombre visible del usuario.
        email (str): Correo electrónico único del usuario.
        password (str): Contraseña en texto plano (`>= 6` caracteres).
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Datos públicos del usuario creado (`id`, `nombre`, `email`).

    Raises:
        ValueError: Si los campos son inválidos o el correo ya está registrado.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError(MENSAJE_NOMBRE_USUARIO_INVALIDO)

    if not isinstance(email, str) or not PATRON_EMAIL_BASICO.match(email.strip()):
        raise ValueError(MENSAJE_EMAIL_INVALIDO)

    password_hash = generate_password_hash(password)
    email_normalizado = email.strip().lower()
    nombre_limpio = nombre.strip()
    creado_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        existente = conn.execute(
            "SELECT id FROM usuarios WHERE email = ?",
            (email_normalizado,),
        ).fetchone()
        if existente is not None:
            raise ValueError(MENSAJE_EMAIL_DUPLICADO)

        cursor = conn.execute(
            """
            INSERT INTO usuarios (nombre, email, password_hash, creado_en)
            VALUES (?, ?, ?, ?)
            """,
            (nombre_limpio, email_normalizado, password_hash, creado_en),
        )
        nuevo_id = int(cursor.lastrowid or 0)

    return {
        "id": nuevo_id,
        "nombre": nombre_limpio,
        "email": email_normalizado,
    }


def autenticar_usuario(
    email: str,
    password: str,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any]:
    """Valida las credenciales de un usuario registrado (HU-12).

    Args:
        email (str): Correo electrónico del usuario.
        password (str): Contraseña en texto plano.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any]: Diccionario con `id`, `nombre` y `email` del usuario.

    Raises:
        ValueError: Si el correo no existe o la contraseña no coincide.
    """
    if not isinstance(email, str) or not isinstance(password, str):
        raise ValueError(MENSAJE_CREDENCIALES_INVALIDAS)

    email_normalizado = email.strip().lower()
    inicializar_db(ruta_db)

    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            """
            SELECT id, nombre, email, password_hash
            FROM usuarios
            WHERE email = ?
            """,
            (email_normalizado,),
        ).fetchone()

    if fila is None or not check_password_hash(str(fila["password_hash"]), password):
        raise ValueError(MENSAJE_CREDENCIALES_INVALIDAS)

    return {
        "id": int(fila["id"]),
        "nombre": str(fila["nombre"]),
        "email": str(fila["email"]),
    }


def obtener_usuario_por_id(
    usuario_id: int,
    *,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> dict[str, Any] | None:
    """Obtiene los datos públicos de un usuario por su identificador.

    Args:
        usuario_id (int): Identificador numérico del usuario.
        ruta_db (str | Path): Ruta de la base de datos SQLite local.

    Returns:
        dict[str, Any] | None: Diccionario con `id`, `nombre` y `email`, o `None`.
    """
    inicializar_db(ruta_db)
    with obtener_conexion(ruta_db) as conn:
        fila = conn.execute(
            "SELECT id, nombre, email FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()

    if fila is None:
        return None
    return {
        "id": int(fila["id"]),
        "nombre": str(fila["nombre"]),
        "email": str(fila["email"]),
    }

"""Aplicación Web Local WSGI para FinanzasPersonales-App (HU-01 a HU-08).

Implementa el servidor web ligero y las rutas HTTP para el panel de control
financiero, registro de gastos en lenguaje natural, configuración de
presupuesto mensual, filtrado offline por categoría, reclasificación con un
clic y exportación a CSV estándar, cumpliendo RNF-01 (< 1,2 s) y RNF-04.
"""

from dataclasses import dataclass
import html
import io
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import make_server

from src.database import (
    CATEGORIAS_VALIDAS,
    RUTA_DB_DEFECTO,
    actualizar_categoria_transaccion,
    guardar_presupuesto,
)
from src.servicios import (
    MENSAJE_MONTO_AMBIGUO,
    exportar_transacciones_csv,
    formatear_pesos,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
)

DIRECTORIO_BASE: Path = Path(__file__).resolve().parent
RUTA_PLANTILLA_INDEX: Path = DIRECTORIO_BASE / "templates" / "index.html"
RUTA_CSS_ESTILOS: Path = DIRECTORIO_BASE / "static" / "style.css"

MAPA_CLASES_BADGE: dict[str, str] = {
    "Transporte/Moto": "badge-moto",
    "Alimentación": "badge-comida",
    "Estudio": "badge-estudio",
    "Ocio": "badge-ocio",
    "Gastos Varios": "badge-varios",
}


@dataclass(frozen=True)
class RespuestaPrueba:
    """Representa una respuesta HTTP capturada por `ClientePruebaWeb`."""

    status_code: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        """Retorna el cuerpo decodificado en UTF-8."""
        return self.body.decode("utf-8")


class ClientePruebaWeb:
    """Cliente de pruebas síncrono en memoria para la aplicación WSGI."""

    def __init__(self, app_wsgi: Callable[..., list[bytes]]) -> None:
        """Inicializa el cliente con la aplicación WSGI objetivo.

        Args:
            app_wsgi (Callable[..., list[bytes]]): Función WSGI invocable.
        """
        self._app = app_wsgi

    def get(
        self,
        ruta: str = "/",
        query_params: dict[str, str] | None = None,
    ) -> RespuestaPrueba:
        """Ejecuta una petición HTTP GET simulada sobre la aplicación WSGI.

        Args:
            ruta (str): Ruta del endpoint (ej. `'/'` o `'/exportar-csv'`).
            query_params (dict[str, str] | None): Parámetros de consulta URL.

        Returns:
            RespuestaPrueba: Objeto con código de estado, cabeceras y cuerpo.
        """
        query_string = urlencode(query_params or {})
        return self._invocar("GET", ruta, query_string=query_string)

    def post(
        self,
        ruta: str,
        data: dict[str, str] | None = None,
    ) -> RespuestaPrueba:
        """Ejecuta una petición HTTP POST con datos de formulario (`urlencoded`).

        Args:
            ruta (str): Ruta del endpoint (ej. `'/gastos'` o `'/presupuesto'`).
            data (dict[str, str] | None): Campos del formulario por enviar.

        Returns:
            RespuestaPrueba: Objeto con código de estado, cabeceras y cuerpo.
        """
        cuerpo = urlencode(data or {}).encode("utf-8")
        return self._invocar("POST", ruta, body=cuerpo)

    def _invocar(
        self,
        metodo: str,
        ruta: str,
        query_string: str = "",
        body: bytes = b"",
    ) -> RespuestaPrueba:
        """Construye el entorno WSGI y captura la respuesta generada.

        Args:
            metodo (str): Método HTTP (`'GET'` o `'POST'`).
            ruta (str): Ruta solicitada.
            query_string (str): Cadena de consulta URL.
            body (bytes): Cuerpo binario de la petición.

        Returns:
            RespuestaPrueba: Respuesta estructurada.
        """
        estado_capturado: list[str] = ["200 OK"]
        cabeceras_capturadas: list[tuple[str, str]] = []

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
        ) -> None:
            estado_capturado[0] = status
            cabeceras_capturadas.extend(headers)

        environ: dict[str, Any] = {
            "REQUEST_METHOD": metodo,
            "PATH_INFO": ruta,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "wsgi.input": io.BytesIO(body),
        }
        fragmentos = self._app(environ, start_response)
        codigo = int(estado_capturado[0].split(" ", maxsplit=1)[0])
        return RespuestaPrueba(
            status_code=codigo,
            headers=dict(cabeceras_capturadas),
            body=b"".join(fragmentos),
        )


def _renderizar_alertas(
    resumen: dict[str, Any],
    mensaje_operacion: str | None,
    tipo_alerta: str | None,
) -> str:
    """Construye los bloques HTML de alertas preventivas y notificaciones.

    Args:
        resumen (dict[str, Any]): Diccionario de métricas financieras del panel.
        mensaje_operacion (str | None): Mensaje resultante de la acción actual.
        tipo_alerta (str | None): Tipo visual (`'exito'`, `'advertencia'`, `'error'`).

    Returns:
        str: Fragmento HTML seguro con los avisos activos.
    """
    bloques: list[str] = []

    if resumen["mensaje_presupuesto"]:
        msg_pres = html.escape(str(resumen["mensaje_presupuesto"]))
        bloques.append(
            f'<div class="alert alert-advertencia" role="alert">{msg_pres}</div>'
        )

    if resumen["alerta_sobregiro"]:
        msg_sob = html.escape(str(resumen["alerta_sobregiro"]))
        bloques.append(
            f'<div class="alert alert-sobregiro" role="alert">{msg_sob}</div>'
        )

    if mensaje_operacion:
        clase = f"alert-{html.escape(tipo_alerta or 'exito')}"
        msg_op = html.escape(mensaje_operacion)
        bloques.append(
            f'<div class="alert {clase}" role="alert">{msg_op}</div>'
        )

    return "\n".join(bloques)


def _renderizar_modal_confirmacion(
    texto_pendiente: str | None,
    mensaje_confirmacion: str | None,
) -> str:
    """Genera el modal HTML cuando un gasto supera el 50% del presupuesto (HU-06).

    Args:
        texto_pendiente (str | None): Frase original que disparó el umbral >50%.
        mensaje_confirmacion (str | None): Mensaje con el porcentaje calculado.

    Returns:
        str: Fragmento HTML del modal con botones Confirmar y Cancelar.
    """
    if not texto_pendiente or not mensaje_confirmacion:
        return ""

    texto_seguro = html.escape(texto_pendiente)
    mensaje_seguro = html.escape(mensaje_confirmacion)
    return (
        '<div class="modal-confirmacion" role="dialog" aria-modal="true">'
        "<h3>Confirmación Preventiva de Gasto Elevado (HU-06)</h3>"
        f"<p>{mensaje_seguro}</p>"
        '<div class="modal-actions">'
        '<form action="/gastos" method="post">'
        f'<input type="hidden" name="texto" value="{texto_seguro}">'
        '<input type="hidden" name="confirmado" value="1">'
        '<button type="submit" class="btn btn-danger btn-sm">Confirmar</button>'
        "</form>"
        '<a href="/" class="btn btn-secondary btn-sm">Cancelar</a>'
        "</div></div>"
    )


def _renderizar_opciones_filtro(categoria_activa: str) -> str:
    """Construye las etiquetas `<option>` para el selector de categorías (HU-07).

    Args:
        categoria_activa (str): Categoría actualmente seleccionada.

    Returns:
        str: Cadena HTML con las opciones del selector.
    """
    opciones = ["Todas", *CATEGORIAS_VALIDAS]
    items_html: list[str] = []
    for opcion in opciones:
        seleccionado = " selected" if opcion == categoria_activa else ""
        op_segura = html.escape(opcion)
        items_html.append(
            f'<option value="{op_segura}"{seleccionado}>{op_segura}</option>'
        )
    return "\n".join(items_html)


def _renderizar_fila_transaccion(tx: dict[str, Any]) -> str:
    """Construye una fila HTML `<tr>` para una transacción individual.

    Args:
        tx (dict[str, Any]): Diccionario con datos de la transacción.

    Returns:
        str: Elemento `<tr>` con celdas y formulario de reclasificación.
    """
    tx_id = int(tx["id"])
    categoria = str(tx["categoria"])
    es_ambiguo = bool(tx["es_ambiguo"])
    clase_fila = ' class="fila-ambigua"' if es_ambiguo else ""
    clase_badge = MAPA_CLASES_BADGE.get(categoria, "badge-varios")
    etiqueta_ambigua = (
        " <small>(Concepto ambiguo: clic para corregir)</small>"
        if es_ambiguo
        else ""
    )

    opciones_html = "".join(
        f'<option value="{html.escape(c)}"'
        f'{" selected" if c == categoria else ""}>{html.escape(c)}</option>'
        for c in CATEGORIAS_VALIDAS
    )
    selector_html = (
        '<form action="/transacciones/categoria" method="post" '
        'class="inline-category-form">'
        f'<input type="hidden" name="transaccion_id" value="{tx_id}">'
        '<select name="nueva_categoria" aria-label="Cambiar categoría">'
        f"{opciones_html}</select>"
        '<button type="submit" class="btn btn-secondary btn-sm">'
        "Cambiar</button></form>"
    )

    return (
        f"<tr{clase_fila}>"
        f"<td>#{tx_id}</td>"
        f"<td>{html.escape(str(tx['fecha']))}</td>"
        f"<td><strong>{html.escape(str(tx['concepto']))}</strong>{etiqueta_ambigua}</td>"
        f"<td><strong>{html.escape(formatear_pesos(int(tx['monto'])))}</strong></td>"
        f'<td><span class="badge {clase_badge}">'
        f"{html.escape(categoria)}</span></td>"
        f"<td>{selector_html}</td>"
        "</tr>"
    )


def _renderizar_tabla_transacciones(resumen: dict[str, Any]) -> str:
    """Construye la tabla HTML de transacciones o el aviso de estado vacío (HU-07).

    Args:
        resumen (dict[str, Any]): Estado financiero y lista de transacciones.

    Returns:
        str: Tabla HTML con soporte para reclasificación rápida en un clic (HU-03).
    """
    if resumen["mensaje_filtro_vacio"]:
        msg_vacio = html.escape(str(resumen["mensaje_filtro_vacio"]))
        return f'<div class="empty-state"><p>{msg_vacio}</p></div>'

    transacciones: list[dict[str, Any]] = resumen["transacciones"]
    if not transacciones:
        return (
            '<div class="empty-state">'
            "<p>Aún no hay gastos registrados. Ingrese su primer gasto arriba.</p>"
            "</div>"
        )

    filas_html = "".join(_renderizar_fila_transaccion(tx) for tx in transacciones)
    return (
        '<div class="table-responsive"><table><thead><tr>'
        "<th>ID</th><th>Fecha</th><th>Concepto</th>"
        "<th>Monto</th><th>Categoría</th><th>Corregir (HU-03)</th>"
        "</tr></thead><tbody>"
        f"{filas_html}"
        "</tbody></table></div>"
    )


def renderizar_pagina_principal(  # pylint: disable=too-many-arguments
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    categoria_filtro: str | None = None,
    mensaje_operacion: str | None = None,
    tipo_alerta: str | None = None,
    texto_pendiente: str | None = None,
    mensaje_confirmacion: str | None = None,
    valor_input_texto: str = "",
) -> str:
    """Renderiza la plantilla `templates/index.html` con el estado actual.

    Args:
        ruta_db (str | Path): Ruta de la base de datos SQLite local.
        categoria_filtro (str | None): Categoría activa para filtrar la tabla.
        mensaje_operacion (str | None): Notificación de la última operación.
        tipo_alerta (str | None): Estilo visual (`'exito'`, `'advertencia'`, `'error'`).
        texto_pendiente (str | None): Frase pendiente de confirmación (>50%).
        mensaje_confirmacion (str | None): Mensaje de confirmación preventiva.
        valor_input_texto (str): Valor por conservar en la caja de texto si hubo error.

    Returns:
        str: Documento HTML5 completo listo para enviar al navegador.
    """
    resumen = obtener_resumen_financiero(
        categoria_filtro=categoria_filtro,
        ruta_db=ruta_db,
    )
    plantilla = RUTA_PLANTILLA_INDEX.read_text(encoding="utf-8")

    if not resumen["presupuesto_configurado"]:
        clase_saldo = ""
        estado_saldo = "Defina su presupuesto en el panel lateral"
    elif resumen["en_sobregiro"]:
        clase_saldo = "card-saldo-negativo"
        estado_saldo = "Saldo en sobregiro (HU-06)"
    else:
        clase_saldo = "card-saldo-positivo"
        estado_saldo = "Dentro del presupuesto mensual"

    reemplazos: dict[str, str] = {
        "{{BLOQUE_ALERTAS}}": _renderizar_alertas(
            resumen, mensaje_operacion, tipo_alerta
        ),
        "{{BLOQUE_MODAL_CONFIRMACION}}": _renderizar_modal_confirmacion(
            texto_pendiente, mensaje_confirmacion
        ),
        "{{VALOR_INPUT_TEXTO}}": html.escape(valor_input_texto),
        "{{PRESUPUESTO_FMT}}": html.escape(str(resumen["presupuesto_fmt"])),
        "{{TOTAL_GASTADO_FMT}}": html.escape(str(resumen["total_gastado_fmt"])),
        "{{TOTAL_REGISTROS}}": str(len(resumen["transacciones"])),
        "{{CLASE_TARJETA_SALDO}}": clase_saldo,
        "{{SALDO_DISPONIBLE_FMT}}": html.escape(str(resumen["saldo_disponible_fmt"])),
        "{{ESTADO_SALDO_TEXTO}}": html.escape(estado_saldo),
        "{{PORCENTAJE_CONSUMO}}": f"{resumen['porcentaje_consumo']:.1f}",
        "{{PORCENTAJE_BARRA}}": f"{resumen['porcentaje_barra']:.1f}",
        "{{CLASE_BARRA_PROGRESO}}": (
            "progress-fill-danger" if resumen["en_sobregiro"] else ""
        ),
        "{{CATEGORIA_ACTIVA}}": html.escape(str(resumen["categoria_activa"])),
        "{{SUBTOTAL_FILTRADO_FMT}}": html.escape(str(resumen["subtotal_filtrado_fmt"])),
        "{{OPCIONES_FILTRO_CATEGORIA}}": _renderizar_opciones_filtro(
            str(resumen["categoria_activa"])
        ),
        "{{CONTENIDO_TABLA_TRANSACCIONES}}": _renderizar_tabla_transacciones(resumen),
        "{{PRESUPUESTO_VALOR_ACTUAL}}": (
            str(resumen["presupuesto_mensual"])
            if resumen["presupuesto_mensual"] is not None
            else ""
        ),
    }

    html_final = plantilla
    for marcador, valor in reemplazos.items():
        html_final = html_final.replace(marcador, valor)
    return html_final


def _leer_formulario_post(environ: dict[str, Any]) -> dict[str, str]:
    """Extrae y decodifica los campos de un formulario HTTP POST.

    Args:
        environ (dict[str, Any]): Diccionario de entorno WSGI.

    Returns:
        dict[str, str]: Mapa de claves y valores enviados en el formulario.
    """
    try:
        longitud = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        longitud = 0

    cuerpo_bytes = environ["wsgi.input"].read(longitud) if longitud > 0 else b""
    parsed = parse_qs(cuerpo_bytes.decode("utf-8"), keep_blank_values=True)
    return {clave: valores[0] if valores else "" for clave, valores in parsed.items()}


def _procesar_post_gastos(
    formulario: dict[str, str],
    ruta_db: str | Path,
) -> str:
    """Procesa el envío del formulario de registro de gasto (`POST /gastos`).

    Args:
        formulario (dict[str, str]): Datos del formulario con `texto` y `confirmado`.
        ruta_db (str | Path): Ruta de la base de datos SQLite.

    Returns:
        str: HTML renderizado con el resultado del registro o alerta preventiva.
    """
    texto = formulario.get("texto", "")
    confirmado = formulario.get("confirmado", "") == "1"

    try:
        resultado = registrar_gasto_desde_texto(
            texto,
            confirmado=confirmado,
            ruta_db=ruta_db,
        )
    except ValueError as err:
        mensaje_err = str(err)
        tipo = "advertencia" if mensaje_err == MENSAJE_MONTO_AMBIGUO else "error"
        return renderizar_pagina_principal(
            ruta_db,
            mensaje_operacion=mensaje_err,
            tipo_alerta=tipo,
            valor_input_texto=texto,
        )

    if resultado["requiere_confirmacion"]:
        return renderizar_pagina_principal(
            ruta_db,
            texto_pendiente=texto,
            mensaje_confirmacion=str(resultado["mensaje"]),
            valor_input_texto=texto,
        )

    return renderizar_pagina_principal(
        ruta_db,
        mensaje_operacion=str(resultado["mensaje"]),
        tipo_alerta="exito",
    )


def _procesar_post_presupuesto(
    formulario: dict[str, str],
    ruta_db: str | Path,
) -> str:
    """Procesa la actualización del presupuesto mensual (`POST /presupuesto`).

    Args:
        formulario (dict[str, str]): Formulario con `monto_mensual`.
        ruta_db (str | Path): Ruta de la base de datos SQLite.

    Returns:
        str: HTML renderizado con el nuevo tope presupuestal o mensaje de error.
    """
    valor_raw = formulario.get("monto_mensual", "").strip().replace(".", "")
    try:
        monto_int = int(valor_raw)
        guardar_presupuesto(monto_int, ruta_db=ruta_db)
    except ValueError:
        return renderizar_pagina_principal(
            ruta_db,
            mensaje_operacion=(
                "El presupuesto mensual debe ser un número positivo mayor a cero"
            ),
            tipo_alerta="error",
        )

    return renderizar_pagina_principal(
        ruta_db,
        mensaje_operacion="Presupuesto mensual actualizado exitosamente",
        tipo_alerta="exito",
    )


def _procesar_post_reclasificacion(
    formulario: dict[str, str],
    ruta_db: str | Path,
) -> str:
    """Procesa el cambio rápido de categoría (`POST /transacciones/categoria`).

    Args:
        formulario (dict[str, str]): Datos con `transaccion_id` y `nueva_categoria`.
        ruta_db (str | Path): Ruta de la base de datos SQLite.

    Returns:
        str: HTML renderizado con la tabla actualizada.
    """
    try:
        tx_id = int(formulario.get("transaccion_id", "0"))
        nueva_cat = formulario.get("nueva_categoria", "")
        actualizar_categoria_transaccion(tx_id, nueva_cat, ruta_db=ruta_db)
        return renderizar_pagina_principal(
            ruta_db,
            mensaje_operacion=f"Categoría actualizada a '{nueva_cat}'",
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def crear_app(
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> Callable[..., list[bytes]]:
    """Crea y configura la aplicación WSGI conectada a la base de datos SQLite.

    Args:
        ruta_db (str | Path): Ruta del archivo SQLite local.

    Returns:
        Callable[..., list[bytes]]: Aplicación WSGI estándar PEP 3333.
    """

    def aplicacion_wsgi(
        environ: dict[str, Any],
        start_response: Callable[[str, list[tuple[str, str]]], None],
    ) -> list[bytes]:
        metodo = environ.get("REQUEST_METHOD", "GET").upper()
        ruta = environ.get("PATH_INFO", "/")

        if metodo == "GET" and ruta == "/static/style.css":
            contenido_css = RUTA_CSS_ESTILOS.read_bytes()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/css; charset=utf-8"),
                    ("Content-Length", str(len(contenido_css))),
                ],
            )
            return [contenido_css]

        if metodo == "GET" and ruta == "/exportar-csv":
            try:
                nombre_csv, contenido_csv = exportar_transacciones_csv(ruta_db=ruta_db)
                cuerpo_csv = contenido_csv.encode("utf-8")
                start_response(
                    "200 OK",
                    [
                        ("Content-Type", "text/csv; charset=utf-8"),
                        (
                            "Content-Disposition",
                            f'attachment; filename="{nombre_csv}"',
                        ),
                        ("Content-Length", str(len(cuerpo_csv))),
                    ],
                )
                return [cuerpo_csv]
            except ValueError as err:
                cuerpo_err = renderizar_pagina_principal(
                    ruta_db,
                    mensaje_operacion=str(err),
                    tipo_alerta="error",
                ).encode("utf-8")
                start_response(
                    "400 Bad Request",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(cuerpo_err))),
                    ],
                )
                return [cuerpo_err]

        if metodo == "POST" and ruta == "/gastos":
            html_resp = _procesar_post_gastos(_leer_formulario_post(environ), ruta_db)
        elif metodo == "POST" and ruta == "/presupuesto":
            html_resp = _procesar_post_presupuesto(
                _leer_formulario_post(environ), ruta_db
            )
        elif metodo == "POST" and ruta == "/transacciones/categoria":
            html_resp = _procesar_post_reclasificacion(
                _leer_formulario_post(environ), ruta_db
            )
        else:
            params = parse_qs(environ.get("QUERY_STRING", ""))
            cat_filtro = params.get("categoria", ["Todas"])[0]
            html_resp = renderizar_pagina_principal(
                ruta_db,
                categoria_filtro=cat_filtro,
            )

        cuerpo_html = html_resp.encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(cuerpo_html))),
            ],
        )
        return [cuerpo_html]

    return aplicacion_wsgi


def iniciar_servidor(
    host: str = "127.0.0.1",
    puerto: int = 5000,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> None:
    """Inicia el servidor web local en el puerto especificado.

    Args:
        host (str): Dirección IP de escucha local (por defecto `'127.0.0.1'`).
        puerto (int): Puerto TCP local (por defecto `5000`).
        ruta_db (str | Path): Ruta de la base de datos SQLite local.
    """
    app = crear_app(ruta_db=ruta_db)
    with make_server(host, puerto, app) as httpd:
        print(f"Servidor activo en http://{host}:{puerto}")
        httpd.serve_forever()


if __name__ == "__main__":
    iniciar_servidor()

"""Aplicación Web Local WSGI para Bolsillo / FinanzasPersonales-App.

Implementa el servidor web multiusuario con autenticación segura (`scrypt`),
navegación mes a mes (`YYYY-MM`) con cierre y arrastre automático de saldo,
analítica visual con Chart.js, gastos fijos recurrentes, control de créditos
a cuotas, buscador instantáneo y exportación a CSV estándar.
"""

from dataclasses import dataclass
import html
from http.cookies import SimpleCookie
import io
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import make_server

from src.auth import (
    autenticar_usuario,
    obtener_usuario_por_id,
    registrar_usuario,
)
from src.database import (
    CATEGORIAS_VALIDAS,
    RUTA_DB_DEFECTO,
    actualizar_categoria_transaccion,
    crear_credito,
    crear_gasto_fijo,
    guardar_meta_ahorro,
    guardar_presupuesto,
)
from src.servicios import (
    MENSAJE_MONTO_AMBIGUO,
    aplicar_gasto_fijo_al_mes,
    cerrar_y_avanzar_mes,
    es_frase_ingreso_extra,
    exportar_transacciones_csv,
    formatear_pesos,
    obtener_resumen_financiero,
    registrar_gasto_desde_texto,
    registrar_ingreso_desde_texto,
    registrar_pago_cuota_credito,
)

DIRECTORIO_BASE: Path = Path(__file__).resolve().parent
RUTA_PLANTILLA_INDEX: Path = DIRECTORIO_BASE / "templates" / "index.html"
RUTA_PLANTILLA_LOGIN: Path = DIRECTORIO_BASE / "templates" / "login.html"
RUTA_PLANTILLA_REGISTER: Path = DIRECTORIO_BASE / "templates" / "register.html"
RUTA_CSS_ESTILOS: Path = DIRECTORIO_BASE / "static" / "style.css"

COOKIE_SESION_USUARIO: str = "bolsillo_uid"

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
    """Cliente de pruebas síncrono en memoria con soporte de cookies de sesión."""

    def __init__(self, app_wsgi: Callable[..., list[bytes]]) -> None:
        """Inicializa el cliente con la aplicación WSGI objetivo."""
        self._app = app_wsgi
        self._cookies: dict[str, str] = {}

    def get(
        self,
        ruta: str = "/",
        query_params: dict[str, str] | None = None,
    ) -> RespuestaPrueba:
        """Ejecuta una petición HTTP GET simulada sobre la aplicación WSGI."""
        query_string = urlencode(query_params or {})
        return self._invocar("GET", ruta, query_string=query_string)

    def post(
        self,
        ruta: str,
        data: dict[str, str] | None = None,
    ) -> RespuestaPrueba:
        """Ejecuta una petición HTTP POST con datos de formulario (`urlencoded`)."""
        cuerpo = urlencode(data or {}).encode("utf-8")
        return self._invocar("POST", ruta, body=cuerpo)

    def _invocar(
        self,
        metodo: str,
        ruta: str,
        query_string: str = "",
        body: bytes = b"",
    ) -> RespuestaPrueba:
        """Construye el entorno WSGI, gestiona cookies y captura la respuesta."""
        estado_capturado: list[str] = ["200 OK"]
        cabeceras_capturadas: list[tuple[str, str]] = []

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
        ) -> None:
            estado_capturado[0] = status
            cabeceras_capturadas.extend(headers)
            for nombre_hdr, valor_hdr in headers:
                if nombre_hdr.lower() == "set-cookie":
                    cookie_obj = SimpleCookie()
                    cookie_obj.load(valor_hdr)
                    for clave_c, morsel in cookie_obj.items():
                        if morsel.value:
                            self._cookies[clave_c] = morsel.value
                        else:
                            self._cookies.pop(clave_c, None)

        cookie_header = "; ".join(
            f"{clave}={valor}" for clave, valor in self._cookies.items()
        )
        environ: dict[str, Any] = {
            "REQUEST_METHOD": metodo,
            "PATH_INFO": ruta,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "HTTP_COOKIE": cookie_header,
            "wsgi.input": io.BytesIO(body),
        }
        fragmentos = self._app(environ, start_response)
        codigo = int(estado_capturado[0].split(" ", maxsplit=1)[0])
        return RespuestaPrueba(
            status_code=codigo,
            headers=dict(cabeceras_capturadas),
            body=b"".join(fragmentos),
        )


def _extraer_usuario_sesion(
    environ: dict[str, Any],
    ruta_db: str | Path,
) -> tuple[int, str]:
    """Obtiene el `(usuario_id, nombre_usuario)` activo desde la cookie de sesión."""
    raw_cookie = environ.get("HTTP_COOKIE", "")
    if raw_cookie:
        cookie_obj = SimpleCookie()
        cookie_obj.load(raw_cookie)
        if COOKIE_SESION_USUARIO in cookie_obj:
            try:
                uid = int(cookie_obj[COOKIE_SESION_USUARIO].value)
                usuario = obtener_usuario_por_id(uid, ruta_db=ruta_db)
                if usuario is not None:
                    return int(usuario["id"]), str(usuario["nombre"])
            except ValueError:
                pass
    return 1, "Espacio Personal"


def renderizar_vista_auth(
    es_registro: bool = False,
    mensaje_error: str | None = None,
) -> str:
    """Renderiza las pantallas minimalistas `/login` o `/register`."""
    ruta_plantilla = RUTA_PLANTILLA_REGISTER if es_registro else RUTA_PLANTILLA_LOGIN
    plantilla = ruta_plantilla.read_text(encoding="utf-8")
    bloque_alerta = (
        f'<div class="alert alert-error" role="alert">'
        f"{html.escape(mensaje_error)}</div>"
        if mensaje_error
        else ""
    )
    return plantilla.replace("{{BLOQUE_ALERTA_AUTH}}", bloque_alerta)


def _renderizar_alertas(
    resumen: dict[str, Any],
    mensaje_operacion: str | None,
    tipo_alerta: str | None,
) -> str:
    """Construye los bloques HTML de alertas preventivas y notificaciones."""
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
    periodo_activo: str,
) -> str:
    """Genera el modal HTML cuando un gasto supera el 50% del presupuesto."""
    if not texto_pendiente or not mensaje_confirmacion:
        return ""

    texto_seguro = html.escape(texto_pendiente)
    mensaje_seguro = html.escape(mensaje_confirmacion)
    per_seguro = html.escape(periodo_activo)
    return (
        '<div class="modal-confirmacion" role="dialog" aria-modal="true">'
        "<h3>Confirmación preventiva de gasto elevado</h3>"
        f"<p>{mensaje_seguro}</p>"
        '<div class="modal-actions">'
        '<form action="/gastos" method="post">'
        f'<input type="hidden" name="periodo" value="{per_seguro}">'
        f'<input type="hidden" name="texto" value="{texto_seguro}">'
        '<input type="hidden" name="confirmado" value="1">'
        '<button type="submit" class="btn btn-danger btn-sm">Confirmar</button>'
        "</form>"
        f'<a href="/?periodo={per_seguro}" class="btn btn-secondary btn-sm">'
        "Cancelar</a></div></div>"
    )


def _renderizar_opciones_filtro(categoria_activa: str) -> str:
    """Construye las etiquetas `<option>` para el selector de categorías."""
    opciones = ["Todas", *CATEGORIAS_VALIDAS]
    items_html: list[str] = []
    for opcion in opciones:
        seleccionado = " selected" if opcion == categoria_activa else ""
        op_segura = html.escape(opcion)
        items_html.append(
            f'<option value="{op_segura}"{seleccionado}>{op_segura}</option>'
        )
    return "\n".join(items_html)


def _renderizar_opciones_categorias_form() -> str:
    """Construye las opciones `<option>` de categorías para formularios."""
    return "\n".join(
        f'<option value="{html.escape(cat)}">{html.escape(cat)}</option>'
        for cat in CATEGORIAS_VALIDAS
    )


def _renderizar_gastos_fijos(
    gastos_fijos: list[dict[str, Any]],
    periodo_activo: str,
) -> str:
    """Renderiza la lista de gastos fijos mensuales con botón de 1 clic."""
    if not gastos_fijos:
        return (
            '<div class="empty-state">'
            "<p>Sin gastos fijos aún. Agrega arriendo, internet o celular abajo.</p>"
            "</div>"
        )

    per_esc = html.escape(periodo_activo)
    items: list[str] = []
    for item in gastos_fijos:
        gf_id = int(item["id"])
        nombre = html.escape(str(item["nombre"]))
        monto_fmt = html.escape(formatear_pesos(int(item["monto"])))
        categoria = html.escape(str(item["categoria"]))
        items.append(
            '<li class="commitment-item">'
            '<div class="commitment-item-top">'
            f'<span class="commitment-title">{nombre}</span>'
            f'<span class="commitment-amount tabular-nums">{monto_fmt}</span>'
            "</div>"
            '<div class="commitment-meta">'
            f"<span>{categoria}</span>"
            '<form action="/gastos-fijos/aplicar" method="post">'
            f'<input type="hidden" name="periodo" value="{per_esc}">'
            f'<input type="hidden" name="gasto_fijo_id" value="{gf_id}">'
            '<button type="submit" class="btn btn-primary btn-sm">'
            "Aplicar al mes</button></form>"
            "</div></li>"
        )
    return f'<ul class="commitment-list">{"".join(items)}</ul>'


def _renderizar_creditos(
    creditos: list[dict[str, Any]],
    periodo_activo: str,
) -> str:
    """Renderiza las obligaciones a cuotas con barra de avance y pago."""
    if not creditos:
        return (
            '<div class="empty-state">'
            "<p>Sin créditos activos. Registra obligaciones a cuotas abajo.</p>"
            "</div>"
        )

    per_esc = html.escape(periodo_activo)
    items: list[str] = []
    for cred in creditos:
        cred_id = int(cred["id"])
        nombre = html.escape(str(cred["nombre"]))
        cuota_fmt = html.escape(formatear_pesos(int(cred["valor_cuota"])))
        pagadas = int(cred["cuotas_pagadas"])
        total = int(cred["total_cuotas"])
        restantes = int(cred["cuotas_restantes"])
        pendiente_fmt = html.escape(formatear_pesos(int(cred["saldo_pendiente"])))
        pct = float(cred["porcentaje_pagado"])
        saldado = bool(cred["pagado_completo"])

        accion_html = (
            '<span class="badge badge-comida">Saldado (100%)</span>'
            if saldado
            else (
                '<form action="/creditos/pagar-cuota" method="post">'
                f'<input type="hidden" name="periodo" value="{per_esc}">'
                f'<input type="hidden" name="credito_id" value="{cred_id}">'
                '<button type="submit" class="btn btn-emerald btn-sm">'
                "Registrar pago de cuota</button></form>"
            )
        )

        items.append(
            '<li class="commitment-item">'
            '<div class="commitment-item-top">'
            f'<span class="commitment-title">{nombre}</span>'
            f'<span class="commitment-amount tabular-nums">{cuota_fmt} / mes</span>'
            "</div>"
            '<div class="mini-progress-track">'
            f'<div class="mini-progress-fill" style="width: {min(pct, 100.0):.1f}%;">'
            "</div></div>"
            '<div class="commitment-meta">'
            f"<span>Cuotas: <b>{pagadas}/{total}</b> "
            f"(faltan {restantes} &bull; {pendiente_fmt})</span>"
            f"{accion_html}"
            "</div></li>"
        )
    return f'<ul class="commitment-list">{"".join(items)}</ul>'


def _renderizar_historial_ingresos(ingresos: list[dict[str, Any]]) -> str:
    """Renderiza la lista lateral de ingresos extra y abonos del mes."""
    if not ingresos:
        return (
            '<div class="empty-state">'
            "<p>Aún no hay ingresos extra en este mes.</p>"
            "</div>"
        )

    items = "".join(
        '<li class="income-mini-item">'
        f'<span>{html.escape(str(ing["concepto"]))}</span>'
        f'<strong class="tabular-nums">'
        f'+{html.escape(formatear_pesos(int(ing["monto"])))}</strong>'
        "</li>"
        for ing in ingresos[:6]
    )
    return f'<ul class="income-mini-list">{items}</ul>'


def _renderizar_fila_transaccion(
    tx: dict[str, Any],
    periodo_activo: str,
) -> str:
    """Construye una fila HTML `<tr>` para una transacción individual."""
    tx_id = int(tx["id"])
    categoria = str(tx["categoria"])
    es_ambiguo = bool(tx["es_ambiguo"])
    clase_fila = ' class="fila-ambigua"' if es_ambiguo else ""
    clase_badge = MAPA_CLASES_BADGE.get(categoria, "badge-varios")
    etiqueta_ambigua = (
        " <small>(Por confirmar categoría)</small>"
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
        f'<input type="hidden" name="periodo" value="{html.escape(periodo_activo)}">'
        f'<input type="hidden" name="transaccion_id" value="{tx_id}">'
        '<select name="nueva_categoria" aria-label="Cambiar categoría">'
        f"{opciones_html}</select>"
        '<button type="submit" class="btn btn-secondary btn-sm">'
        "Cambiar</button></form>"
    )

    return (
        f"<tr{clase_fila}>"
        f'<td class="tabular-nums">#{tx_id}</td>'
        f'<td class="tabular-nums">{html.escape(str(tx["fecha"]))}</td>'
        f"<td><strong>{html.escape(str(tx['concepto']))}</strong>{etiqueta_ambigua}</td>"
        f'<td class="tabular-nums">'
        f"<strong>{html.escape(formatear_pesos(int(tx['monto'])))}</strong></td>"
        f'<td><span class="badge {clase_badge}">'
        f"{html.escape(categoria)}</span></td>"
        f"<td>{selector_html}</td>"
        "</tr>"
    )


def _renderizar_tabla_transacciones(resumen: dict[str, Any]) -> str:
    """Construye la tabla HTML de transacciones o el aviso de estado vacío."""
    if resumen["mensaje_filtro_vacio"]:
        msg_vacio = html.escape(str(resumen["mensaje_filtro_vacio"]))
        return f'<div class="empty-state"><p>{msg_vacio}</p></div>'

    transacciones: list[dict[str, Any]] = resumen["transacciones"]
    if not transacciones:
        return (
            '<div class="empty-state">'
            "<p>Aún no hay movimientos registrados en este periodo.</p>"
            "</div>"
        )

    periodo_act = str(resumen["periodo_activo"])
    filas_html = "".join(
        _renderizar_fila_transaccion(tx, periodo_act) for tx in transacciones
    )
    return (
        '<div class="table-responsive"><table><thead><tr>'
        "<th>ID</th><th>Fecha</th><th>Concepto</th>"
        "<th>Monto</th><th>Categoría</th><th>Ajustar categoría</th>"
        "</tr></thead><tbody>"
        f"{filas_html}"
        "</tbody></table></div>"
    )


def renderizar_pagina_principal(  # pylint: disable=too-many-arguments,too-many-locals
    ruta_db: str | Path = RUTA_DB_DEFECTO,
    *,
    usuario_id: int = 1,
    nombre_usuario: str = "Espacio Personal",
    periodo: str | None = None,
    categoria_filtro: str | None = None,
    busqueda: str | None = None,
    mensaje_operacion: str | None = None,
    tipo_alerta: str | None = None,
    texto_pendiente: str | None = None,
    mensaje_confirmacion: str | None = None,
    valor_input_texto: str = "",
) -> str:
    """Renderiza la plantilla `templates/index.html` con el estado consolidado."""
    resumen = obtener_resumen_financiero(
        categoria_filtro=categoria_filtro,
        ruta_db=ruta_db,
        usuario_id=usuario_id,
        periodo=periodo,
        busqueda=busqueda,
    )
    plantilla = RUTA_PLANTILLA_INDEX.read_text(encoding="utf-8")

    if not resumen["presupuesto_configurado"]:
        clase_saldo = ""
        estado_saldo = "Configura tu presupuesto en el panel lateral"
    elif resumen["en_sobregiro"]:
        clase_saldo = "card-saldo-negativo"
        estado_saldo = "Saldo en rojo: registra un ingreso extra para cubrirlo"
    else:
        clase_saldo = "card-saldo-positivo"
        estado_saldo = "Liquidez positiva disponible"

    periodo_act = str(resumen["periodo_activo"])
    datos_flujo = {
        "Presupuesto": int(resumen["presupuesto_mensual"] or 0),
        "Ingresos Extra": int(resumen["total_ingresos_extra"]),
        "Meta Ahorro": int(resumen["meta_ahorro"]),
        "Gastado": int(resumen["total_gastado"]),
    }

    reemplazos: dict[str, str] = {
        "{{NOMBRE_USUARIO}}": html.escape(nombre_usuario),
        "{{PERIODO_ACTIVO}}": html.escape(periodo_act),
        "{{ETIQUETA_PERIODO}}": html.escape(str(resumen["etiqueta_periodo"])),
        "{{PERIODO_ANTERIOR}}": html.escape(str(resumen["periodo_anterior"])),
        "{{PERIODO_SIGUIENTE}}": html.escape(str(resumen["periodo_siguiente"])),
        "{{BLOQUE_ALERTAS}}": _renderizar_alertas(
            resumen, mensaje_operacion, tipo_alerta
        ),
        "{{BLOQUE_MODAL_CONFIRMACION}}": _renderizar_modal_confirmacion(
            texto_pendiente, mensaje_confirmacion, periodo_act
        ),
        "{{VALOR_INPUT_TEXTO}}": html.escape(valor_input_texto),
        "{{PRESUPUESTO_FMT}}": html.escape(str(resumen["presupuesto_fmt"])),
        "{{SALDO_ARRASTRADO_FMT}}": html.escape(str(resumen["saldo_arrastrado_fmt"])),
        "{{TOTAL_INGRESOS_EXTRA_FMT}}": html.escape(
            str(resumen["total_ingresos_extra_fmt"])
        ),
        "{{CAPACIDAD_TOTAL_FMT}}": html.escape(str(resumen["capacidad_total_fmt"])),
        "{{TOTAL_GASTADO_FMT}}": html.escape(str(resumen["total_gastado_fmt"])),
        "{{TOTAL_REGISTROS}}": str(len(resumen["transacciones"])),
        "{{CLASE_TARJETA_SALDO}}": clase_saldo,
        "{{SALDO_DISPONIBLE_FMT}}": html.escape(str(resumen["saldo_disponible_fmt"])),
        "{{ESTADO_SALDO_TEXTO}}": html.escape(estado_saldo),
        "{{PRESUPUESTO_DIARIO_FMT}}": html.escape(
            str(resumen["presupuesto_diario_fmt"])
        ),
        "{{META_AHORRO_FMT}}": html.escape(str(resumen["meta_ahorro_fmt"])),
        "{{META_AHORRO_VALOR_ACTUAL}}": str(resumen["meta_ahorro"]),
        "{{PORCENTAJE_CONSUMO}}": f"{resumen['porcentaje_consumo']:.1f}",
        "{{PORCENTAJE_BARRA}}": f"{resumen['porcentaje_barra']:.1f}",
        "{{CLASE_BARRA_PROGRESO}}": (
            "progress-fill-danger" if resumen["en_sobregiro"] else ""
        ),
        "{{CATEGORIA_ACTIVA}}": html.escape(str(resumen["categoria_activa"])),
        "{{BUSQUEDA_ACTIVA}}": html.escape(str(resumen["busqueda_activa"])),
        "{{SUBTOTAL_FILTRADO_FMT}}": html.escape(str(resumen["subtotal_filtrado_fmt"])),
        "{{OPCIONES_FILTRO_CATEGORIA}}": _renderizar_opciones_filtro(
            str(resumen["categoria_activa"])
        ),
        "{{OPCIONES_CATEGORIAS_FORM}}": _renderizar_opciones_categorias_form(),
        "{{TOTAL_GASTOS_FIJOS_FMT}}": html.escape(
            str(resumen["total_gastos_fijos_fmt"])
        ),
        "{{BLOQUE_LISTA_GASTOS_FIJOS}}": _renderizar_gastos_fijos(
            resumen["gastos_fijos"], periodo_act
        ),
        "{{TOTAL_CUOTAS_ACTIVAS_FMT}}": html.escape(
            str(resumen["total_cuotas_activas_fmt"])
        ),
        "{{BLOQUE_LISTA_CREDITOS}}": _renderizar_creditos(
            resumen["creditos"], periodo_act
        ),
        "{{BLOQUE_HISTORIAL_INGRESOS}}": _renderizar_historial_ingresos(
            resumen["ingresos_extra"]
        ),
        "{{CONTENIDO_TABLA_TRANSACCIONES}}": _renderizar_tabla_transacciones(resumen),
        "{{PRESUPUESTO_VALOR_ACTUAL}}": (
            str(resumen["presupuesto_mensual"])
            if resumen["presupuesto_mensual"] is not None
            else ""
        ),
        "{{DATOS_JSON_CATEGORIAS}}": json.dumps(resumen["gastos_por_categoria"]),
        "{{DATOS_JSON_FLUJO}}": json.dumps(datos_flujo),
    }

    html_final = plantilla
    for marcador, valor in reemplazos.items():
        html_final = html_final.replace(marcador, valor)
    return html_final


def _leer_formulario_post(environ: dict[str, Any]) -> dict[str, str]:
    """Extrae y decodifica los campos de un formulario HTTP POST."""
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
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Procesa el envío de un gasto o ingreso extra (`POST /gastos`)."""
    texto = formulario.get("texto", "")
    tipo_mov = formulario.get("tipo_movimiento", "gasto").strip().lower()
    confirmado = formulario.get("confirmado", "") == "1"
    periodo = formulario.get("periodo") or None

    try:
        if tipo_mov == "ingreso" or (
            not confirmado and es_frase_ingreso_extra(texto)
        ):
            resultado = registrar_ingreso_desde_texto(
                texto,
                usuario_id=usuario_id,
                periodo=periodo,
                ruta_db=ruta_db,
            )
        else:
            resultado = registrar_gasto_desde_texto(
                texto,
                confirmado=confirmado,
                usuario_id=usuario_id,
                periodo=periodo,
                ruta_db=ruta_db,
            )
    except ValueError as err:
        mensaje_err = str(err)
        tipo = "advertencia" if mensaje_err == MENSAJE_MONTO_AMBIGUO else "error"
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=mensaje_err,
            tipo_alerta=tipo,
            valor_input_texto=texto,
        )

    if resultado.get("requiere_confirmacion"):
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            texto_pendiente=texto,
            mensaje_confirmacion=str(resultado["mensaje"]),
            valor_input_texto=texto,
        )

    return renderizar_pagina_principal(
        ruta_db,
        usuario_id=usuario_id,
        nombre_usuario=nombre_usuario,
        periodo=periodo,
        mensaje_operacion=str(resultado["mensaje"]),
        tipo_alerta="exito",
    )


def _procesar_post_presupuesto(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Procesa la actualización del presupuesto mensual (`POST /presupuesto`)."""
    valor_raw = formulario.get("monto_mensual", "").strip().replace(".", "")
    periodo = formulario.get("periodo") or None
    try:
        monto_int = int(valor_raw)
        guardar_presupuesto(
            monto_int,
            ruta_db=ruta_db,
            usuario_id=usuario_id,
            periodo=periodo,
        )
    except ValueError:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=(
                "El presupuesto mensual debe ser un número positivo mayor a cero"
            ),
            tipo_alerta="error",
        )

    return renderizar_pagina_principal(
        ruta_db,
        usuario_id=usuario_id,
        nombre_usuario=nombre_usuario,
        periodo=periodo,
        mensaje_operacion="Presupuesto mensual actualizado exitosamente",
        tipo_alerta="exito",
    )


def _procesar_post_meta_ahorro(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Procesa la actualización de la meta de ahorro mensual (`POST /meta-ahorro`)."""
    valor_raw = formulario.get("meta_ahorro", "0").strip().replace(".", "")
    periodo = formulario.get("periodo") or None
    try:
        guardar_meta_ahorro(
            int(valor_raw),
            usuario_id=usuario_id,
            periodo=periodo,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion="Meta de ahorro actualizada exitosamente",
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_cerrar_periodo(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Cierra el mes actual y arrastra el saldo al siguiente periodo."""
    periodo_actual = formulario.get("periodo_actual") or None
    try:
        cierre = cerrar_y_avanzar_mes(
            usuario_id=usuario_id,
            periodo_actual=periodo_actual,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=str(cierre["nuevo_periodo"]),
            mensaje_operacion=str(cierre["mensaje"]),
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo_actual,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_reclasificacion(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Procesa el cambio rápido de categoría (`POST /transacciones/categoria`)."""
    periodo = formulario.get("periodo") or None
    try:
        tx_id = int(formulario.get("transaccion_id", "0"))
        nueva_cat = formulario.get("nueva_categoria", "")
        actualizar_categoria_transaccion(
            tx_id,
            nueva_cat,
            ruta_db=ruta_db,
            usuario_id=usuario_id,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=f"Categoría actualizada a '{nueva_cat}'",
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_crear_gasto_fijo(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Crea una plantilla de gasto fijo mensual (`POST /gastos-fijos`)."""
    nombre = formulario.get("nombre", "")
    monto_raw = formulario.get("monto", "").strip().replace(".", "")
    categoria = formulario.get("categoria", "Gastos Varios")
    periodo = formulario.get("periodo") or None
    try:
        crear_gasto_fijo(
            nombre,
            int(monto_raw),
            categoria,
            usuario_id=usuario_id,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion="Gasto fijo mensual guardado exitosamente",
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_aplicar_gasto_fijo(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Aplica un gasto fijo mensual al balance (`POST /gastos-fijos/aplicar`)."""
    periodo = formulario.get("periodo") or None
    try:
        gf_id = int(formulario.get("gasto_fijo_id", "0"))
        res = aplicar_gasto_fijo_al_mes(
            gf_id,
            usuario_id=usuario_id,
            periodo=periodo,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(res["mensaje"]),
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_crear_credito(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Crea un nuevo crédito a cuotas (`POST /creditos`)."""
    nombre = formulario.get("nombre", "")
    cuota_raw = formulario.get("valor_cuota", "").strip().replace(".", "")
    total_raw = formulario.get("total_cuotas", "").strip()
    pagadas_raw = formulario.get("cuotas_pagadas", "0").strip() or "0"
    categoria = formulario.get("categoria", "Gastos Varios")
    periodo = formulario.get("periodo") or None
    try:
        crear_credito(
            nombre=nombre,
            valor_cuota=int(cuota_raw),
            total_cuotas=int(total_raw),
            cuotas_pagadas=int(pagadas_raw),
            categoria=categoria,
            usuario_id=usuario_id,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion="Crédito a cuotas registrado exitosamente",
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _procesar_post_pagar_cuota(
    formulario: dict[str, str],
    ruta_db: str | Path,
    usuario_id: int,
    nombre_usuario: str,
) -> str:
    """Registra el pago de una cuota mensual (`POST /creditos/pagar-cuota`)."""
    periodo = formulario.get("periodo") or None
    try:
        cred_id = int(formulario.get("credito_id", "0"))
        res = registrar_pago_cuota_credito(
            cred_id,
            usuario_id=usuario_id,
            periodo=periodo,
            ruta_db=ruta_db,
        )
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(res["mensaje"]),
            tipo_alerta="exito",
        )
    except ValueError as err:
        return renderizar_pagina_principal(
            ruta_db,
            usuario_id=usuario_id,
            nombre_usuario=nombre_usuario,
            periodo=periodo,
            mensaje_operacion=str(err),
            tipo_alerta="error",
        )


def _responder_html(
    start_response: Callable[[str, list[tuple[str, str]]], None],
    html_str: str,
    status: str = "200 OK",
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    """Envía una respuesta HTML codificada en UTF-8 con cabeceras opcionales."""
    cuerpo = html_str.encode("utf-8")
    cabeceras = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(cuerpo))),
    ]
    if extra_headers:
        cabeceras.extend(extra_headers)
    start_response(status, cabeceras)
    return [cuerpo]


def crear_app(  # pylint: disable=too-many-statements
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> Callable[..., list[bytes]]:
    """Crea y configura la aplicación WSGI conectada a la base de datos SQLite."""
    rutas_post: dict[
        str,
        Callable[[dict[str, str], str | Path, int, str], str],
    ] = {
        "/gastos": _procesar_post_gastos,
        "/ingresos": lambda form, db, uid, nom: _procesar_post_gastos(
            {**form, "tipo_movimiento": "ingreso"}, db, uid, nom
        ),
        "/presupuesto": _procesar_post_presupuesto,
        "/meta-ahorro": _procesar_post_meta_ahorro,
        "/periodo/cerrar": _procesar_post_cerrar_periodo,
        "/transacciones/categoria": _procesar_post_reclasificacion,
        "/gastos-fijos": _procesar_post_crear_gasto_fijo,
        "/gastos-fijos/aplicar": _procesar_post_aplicar_gasto_fijo,
        "/creditos": _procesar_post_crear_credito,
        "/creditos/pagar-cuota": _procesar_post_pagar_cuota,
    }

    def aplicacion_wsgi(  # pylint: disable=too-many-return-statements
        environ: dict[str, Any],
        start_response: Callable[[str, list[tuple[str, str]]], None],
    ) -> list[bytes]:
        metodo = environ.get("REQUEST_METHOD", "GET").upper()
        ruta = environ.get("PATH_INFO", "/")
        usuario_id, nombre_usuario = _extraer_usuario_sesion(environ, ruta_db)

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

        if ruta == "/login":
            if metodo == "GET":
                return _responder_html(
                    start_response,
                    renderizar_vista_auth(es_registro=False),
                )
            form = _leer_formulario_post(environ)
            try:
                user = autenticar_usuario(
                    form.get("email", ""),
                    form.get("password", ""),
                    ruta_db=ruta_db,
                )
                cookie_hdr = (
                    f"{COOKIE_SESION_USUARIO}={user['id']}; "
                    "Path=/; HttpOnly; SameSite=Lax"
                )
                html_panel = renderizar_pagina_principal(
                    ruta_db,
                    usuario_id=int(user["id"]),
                    nombre_usuario=str(user["nombre"]),
                    mensaje_operacion=f"Bienvenido de nuevo, {user['nombre']}",
                    tipo_alerta="exito",
                )
                return _responder_html(
                    start_response,
                    html_panel,
                    extra_headers=[("Set-Cookie", cookie_hdr)],
                )
            except ValueError as err:
                return _responder_html(
                    start_response,
                    renderizar_vista_auth(es_registro=False, mensaje_error=str(err)),
                    status="401 Unauthorized",
                )

        if ruta == "/register":
            if metodo == "GET":
                return _responder_html(
                    start_response,
                    renderizar_vista_auth(es_registro=True),
                )
            form = _leer_formulario_post(environ)
            try:
                user = registrar_usuario(
                    form.get("nombre", ""),
                    form.get("email", ""),
                    form.get("password", ""),
                    ruta_db=ruta_db,
                )
                cookie_hdr = (
                    f"{COOKIE_SESION_USUARIO}={user['id']}; "
                    "Path=/; HttpOnly; SameSite=Lax"
                )
                html_panel = renderizar_pagina_principal(
                    ruta_db,
                    usuario_id=int(user["id"]),
                    nombre_usuario=str(user["nombre"]),
                    mensaje_operacion=(
                        f"Cuenta creada exitosamente. Hola, {user['nombre']}"
                    ),
                    tipo_alerta="exito",
                )
                return _responder_html(
                    start_response,
                    html_panel,
                    extra_headers=[("Set-Cookie", cookie_hdr)],
                )
            except ValueError as err:
                return _responder_html(
                    start_response,
                    renderizar_vista_auth(es_registro=True, mensaje_error=str(err)),
                    status="400 Bad Request",
                )

        if metodo == "POST" and ruta == "/logout":
            cookie_clear = f"{COOKIE_SESION_USUARIO}=; Path=/; Max-Age=0"
            return _responder_html(
                start_response,
                renderizar_vista_auth(es_registro=False),
                extra_headers=[("Set-Cookie", cookie_clear)],
            )

        if metodo == "GET" and ruta == "/exportar-csv":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            periodo_q = params.get("periodo", [None])[0]
            try:
                nombre_csv, contenido_csv = exportar_transacciones_csv(
                    ruta_db=ruta_db,
                    usuario_id=usuario_id,
                    periodo=periodo_q,
                )
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
                return _responder_html(
                    start_response,
                    renderizar_pagina_principal(
                        ruta_db,
                        usuario_id=usuario_id,
                        nombre_usuario=nombre_usuario,
                        periodo=periodo_q,
                        mensaje_operacion=str(err),
                        tipo_alerta="error",
                    ),
                    status="400 Bad Request",
                )

        manejador_post = rutas_post.get(ruta) if metodo == "POST" else None
        if manejador_post is not None:
            html_resp = manejador_post(
                _leer_formulario_post(environ),
                ruta_db,
                usuario_id,
                nombre_usuario,
            )
        else:
            params = parse_qs(environ.get("QUERY_STRING", ""))
            cat_filtro = params.get("categoria", ["Todas"])[0]
            periodo_q = params.get("periodo", [None])[0]
            busqueda_q = params.get("busqueda", [None])[0]
            html_resp = renderizar_pagina_principal(
                ruta_db,
                usuario_id=usuario_id,
                nombre_usuario=nombre_usuario,
                periodo=periodo_q,
                categoria_filtro=cat_filtro,
                busqueda=busqueda_q,
            )

        return _responder_html(start_response, html_resp)

    return aplicacion_wsgi


def iniciar_servidor(
    host: str = "127.0.0.1",
    puerto: int = 5000,
    ruta_db: str | Path = RUTA_DB_DEFECTO,
) -> None:
    """Inicia el servidor web local en el puerto especificado."""
    app = crear_app(ruta_db=ruta_db)
    with make_server(host, puerto, app) as httpd:
        print(f"Bolsillo activo en http://{host}:{puerto}")
        httpd.serve_forever()


if __name__ == "__main__":
    iniciar_servidor()

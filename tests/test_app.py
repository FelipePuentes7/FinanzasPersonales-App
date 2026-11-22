"""Pruebas de integración de rutas web, interfaz HTML y rendimiento (app.py)."""

from pathlib import Path
import time

from app import ClientePruebaWeb, crear_app


def test_panel_principal_autofocus_y_presupuesto_no_establecido(
    tmp_path: Path,
) -> None:
    """Verifica HU-04 Esc. 2 y RNF-04: autofocus en input y aviso de presupuesto."""
    ruta_db = tmp_path / "test_web.db"
    cliente = ClientePruebaWeb(crear_app(ruta_db))

    resp = cliente.get("/")
    assert resp.status_code == 200
    assert "autofocus" in resp.text
    assert (
        "Presupuesto mensual no establecido. Ingrese su presupuesto en la barra "
        "lateral para calcular su saldo"
    ) in resp.text


def test_guardar_presupuesto_y_rechazar_negativo_web(tmp_path: Path) -> None:
    """Verifica HU-05 Esc. 1 y 2 desde el formulario web `/presupuesto`."""
    ruta_db = tmp_path / "test_web.db"
    cliente = ClientePruebaWeb(crear_app(ruta_db))

    resp_err = cliente.post("/presupuesto", {"monto_mensual": "-50000"})
    assert resp_err.status_code == 200
    assert (
        "El presupuesto mensual debe ser un número positivo mayor a cero"
        in resp_err.text
    )

    resp_ok = cliente.post("/presupuesto", {"monto_mensual": "600000"})
    assert resp_ok.status_code == 200
    assert "$600.000" in resp_ok.text


def test_flujo_completo_gastos_alertas_y_reclasificacion_web(tmp_path: Path) -> None:
    """Verifica HU-01, HU-02, HU-03 y HU-06 en las rutas `/gastos` y reclasificación."""
    ruta_db = tmp_path / "test_web.db"
    cliente = ClientePruebaWeb(crear_app(ruta_db))
    cliente.post("/presupuesto", {"monto_mensual": "400000"})

    resp_ok = cliente.post("/gastos", {"texto": "almuerzo corriente 14000"})
    assert "Gasto registrado exitosamente" in resp_ok.text
    assert "Almuerzo corriente" in resp_ok.text
    assert "Alimentación" in resp_ok.text

    resp_sin_monto = cliente.post(
        "/gastos", {"texto": "tanqueé la moto en la mañana"}
    )
    assert (
        "No se detectó un valor monetario válido. Ingrese el monto del gasto"
        in resp_sin_monto.text
    )

    resp_ambiguo = cliente.post("/gastos", {"texto": "gasté media luca en dulces"})
    assert (
        "Monto ambiguo. Por favor indique el valor en cifras numéricas"
        in resp_ambiguo.text
    )

    resp_modal = cliente.post("/gastos", {"texto": "reparación motora 250000"})
    assert "62.5%" in resp_modal.text
    assert "¿Desea confirmar el registro?" in resp_modal.text

    resp_confirmado = cliente.post(
        "/gastos", {"texto": "reparación motora 250000", "confirmado": "1"}
    )
    assert "Gasto registrado exitosamente" in resp_confirmado.text

    resp_asunto = cliente.post("/gastos", {"texto": "pago asunto x 30000"})
    assert "fila-ambigua" in resp_asunto.text

    resp_reclas = cliente.post(
        "/transacciones/categoria",
        {"transaccion_id": "3", "nueva_categoria": "Estudio"},
    )
    assert "Categoría actualizada" in resp_reclas.text


def test_filtrado_offline_exportacion_csv_y_rendimiento_rnf01(tmp_path: Path) -> None:
    """Verifica HU-07, HU-08 y RNF-01 (renderizado < 1.2 segundos)."""
    ruta_db = tmp_path / "test_web.db"
    cliente = ClientePruebaWeb(crear_app(ruta_db))

    resp_csv_vacio = cliente.get("/exportar-csv")
    assert resp_csv_vacio.status_code == 400
    assert (
        "Operación no disponible: No existen transacciones para exportar"
        in resp_csv_vacio.text
    )

    cliente.post("/gastos", {"texto": "20 lucas de gasolina para la moto"})

    resp_filtro_moto = cliente.get("/", {"categoria": "Transporte/Moto"})
    assert "Gasolina para la moto" in resp_filtro_moto.text
    assert "$20.000" in resp_filtro_moto.text

    resp_filtro_ocio = cliente.get("/", {"categoria": "Ocio"})
    assert (
        "No se encontraron transacciones registradas para la categoría "
        "&#x27;Ocio&#x27; en este periodo" in resp_filtro_ocio.text
    )

    inicio = time.perf_counter()
    resp_csv = cliente.get("/exportar-csv")
    duracion = time.perf_counter() - inicio

    assert resp_csv.status_code == 200
    assert "id,fecha,concepto,monto,categoria" in resp_csv.text
    assert duracion < 1.2

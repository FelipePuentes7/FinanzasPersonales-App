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


def test_flujo_web_ingresos_extra_gastos_fijos_y_creditos(tmp_path: Path) -> None:
    """Verifica HU-09, HU-10 y HU-11 desde las rutas HTTP del panel web."""
    ruta_db = tmp_path / "test_web_sdlc.db"
    cliente = ClientePruebaWeb(crear_app(ruta_db))
    cliente.post("/presupuesto", {"monto_mensual": "2000000"})

    # 1. Gasto grande deja el saldo en sobregiro (-$1.000.000)
    resp_sobregiro = cliente.post(
        "/gastos",
        {"texto": "reparación moto 3000000", "confirmado": "1"},
    )
    assert "-$1.000.000" in resp_sobregiro.text
    assert "[ALERTA DE SOBREGIRO]" in resp_sobregiro.text

    # 2. HU-09: Ingreso extra en lenguaje natural recupera el saldo a +$200.000
    resp_ingreso = cliente.post(
        "/gastos",
        {"texto": "me entraron 1.200.000 de trabajo extra"},
    )
    assert "Ingreso extra registrado exitosamente" in resp_ingreso.text
    assert "$200.000 disponible" in resp_ingreso.text
    assert "[ALERTA DE SOBREGIRO]" not in resp_ingreso.text

    # 3. HU-10: Crear y aplicar gasto fijo mensual con 1 clic
    resp_crear_fijo = cliente.post(
        "/gastos-fijos",
        {"nombre": "Internet fibra", "monto": "80000", "categoria": "Estudio"},
    )
    assert "Gasto fijo mensual guardado exitosamente" in resp_crear_fijo.text

    resp_aplicar_fijo = cliente.post(
        "/gastos-fijos/aplicar",
        {"gasto_fijo_id": "1"},
    )
    assert "Gasto fijo aplicado al mes exitosamente" in resp_aplicar_fijo.text
    assert "Gasto fijo: Internet fibra" in resp_aplicar_fijo.text
    assert "$120.000 disponible" in resp_aplicar_fijo.text

    # 4. HU-11: Crear crédito a cuotas y registrar pago de cuota con 1 clic
    resp_crear_cred = cliente.post(
        "/creditos",
        {
            "nombre": "Casco Certificado",
            "valor_cuota": "50000",
            "total_cuotas": "2",
            "cuotas_pagadas": "1",
            "categoria": "Transporte/Moto",
        },
    )
    assert "Crédito a cuotas registrado exitosamente" in resp_crear_cred.text
    assert "1/2" in resp_crear_cred.text

    resp_pagar_cuota = cliente.post(
        "/creditos/pagar-cuota",
        {"credito_id": "1"},
    )
    assert "Pago de cuota registrado exitosamente" in resp_pagar_cuota.text
    assert "Cuota 2/2: Casco Certificado" in resp_pagar_cuota.text
    assert "$70.000 disponible" in resp_pagar_cuota.text

    # 5. HU-11 Esc. 2: Intentar pagar una cuota adicional cuando ya está 2/2
    resp_saldado = cliente.post(
        "/creditos/pagar-cuota",
        {"credito_id": "1"},
    )
    assert "Este crédito ya tiene todas sus cuotas pagadas" in resp_saldado.text


def test_flujo_web_multiusuario_login_rollover_y_sin_jerga_academica(
    tmp_path: Path,
) -> None:
    """Verifica registro/login web, aislamiento entre usuarios, rollover y UI limpia."""
    ruta_db = tmp_path / "test_web_multi.db"
    app_wsgi = crear_app(ruta_db)
    cliente_a = ClientePruebaWeb(app_wsgi)
    cliente_b = ClientePruebaWeb(app_wsgi)

    # 1. Pantallas de login y registro cargan con logo SVG y sin jerga académica
    vista_login = cliente_a.get("/login")
    assert vista_login.status_code == 200
    assert "<svg" in vista_login.text
    assert "Bolsillo" in vista_login.text

    # 2. Registro de Usuario A y configuración de Octubre 2026
    reg_a = cliente_a.post(
        "/register",
        {
            "nombre": "Laura Martínez",
            "email": "laura@bolsillo.co",
            "password": "ClaveLaura2026",
        },
    )
    assert reg_a.status_code == 200
    assert "Laura Martínez" in reg_a.text
    assert "HU-0" not in reg_a.text
    assert "SQLite" not in reg_a.text

    cliente_a.post(
        "/presupuesto",
        {"monto_mensual": "1000000", "periodo": "2026-10"},
    )
    cliente_a.post(
        "/gastos",
        {"texto": "almuerzo ejecutivo 200000", "periodo": "2026-10"},
    )

    # 3. Cierre de Octubre 2026 -> Arrastra +$800.000 de ganancia a Noviembre 2026
    resp_cierre = cliente_a.post(
        "/periodo/cerrar",
        {"periodo_actual": "2026-10"},
    )
    assert resp_cierre.status_code == 200
    assert "Noviembre 2026" in resp_cierre.text
    assert "$1.800.000 disponible" in resp_cierre.text
    assert "chartCategorias" in resp_cierre.text
    assert "chartFlujo" in resp_cierre.text

    # 4. Registro de Usuario B: su sesión está aislada y no ve los datos de Laura
    reg_b = cliente_b.post(
        "/register",
        {
            "nombre": "Mateo Ruiz",
            "email": "mateo@bolsillo.co",
            "password": "ClaveMateo2026",
        },
    )
    assert reg_b.status_code == 200
    assert "Mateo Ruiz" in reg_b.text
    assert "Almuerzo ejecutivo" not in reg_b.text

    # 5. Logout y Login de Laura
    resp_logout = cliente_a.post("/logout")
    assert resp_logout.status_code == 200
    resp_login_err = cliente_a.post(
        "/login",
        {"email": "laura@bolsillo.co", "password": "MalPassword"},
    )
    assert resp_login_err.status_code == 401

"""Generador de reportes profesionales en formato Excel (.xlsx) multi-hoja.

Construye un libro Excel estructurado con 3 hojas:
1. 'Resumen Mensual': Indicadores clave del periodo, ritmo de gasto y desglose
   por categoría con formato de moneda ($#,##0).
2. 'Movimientos': Tabla filtrable de ingresos extra y gastos con fecha, tipo,
   concepto, categoría, sub-etiqueta y monto.
3. 'Compromisos y Créditos': Estado de gastos fijos recurrentes y avance de
   cuotas de créditos activos.

Utiliza `openpyxl` cuando está instalado en el entorno y cuenta con un motor
OOXML (.xlsx) nativo de respaldo para garantizar disponibilidad 100% offline.
"""

import io
from typing import Any
from xml.sax.saxutils import escape
import zipfile


def _construir_filas_hojas(
    resumen: dict[str, Any],
    nombre_usuario: str,
) -> tuple[list[list[Any]], list[list[Any]], list[list[Any]]]:
    """Prepara las matrices de datos para las 3 hojas del libro Excel.

    Args:
        resumen (dict[str, Any]): Estado financiero consolidado del periodo.
        nombre_usuario (str): Nombre visible del titular de la cuenta.

    Returns:
        tuple[list[list[Any]], list[list[Any]], list[list[Any]]]: Tupla con las
            filas de `(hoja_resumen, hoja_movimientos, hoja_compromisos)`.
    """
    ritmo = resumen.get("ritmo_gasto", {})
    hoja_resumen: list[list[Any]] = [
        ["BOLSILLO v1.0 - REPORTE FINANCIERO MENSUAL", ""],
        ["Periodo", str(resumen.get("etiqueta_periodo", ""))],
        ["Titular", nombre_usuario],
        ["Estado del Ritmo de Gasto", str(ritmo.get("estado", "Normal"))],
        ["", ""],
        ["INDICADOR GENERAL", "VALOR (COP)"],
        ["Presupuesto Base del Mes", int(resumen.get("presupuesto_mensual") or 0)],
        ["Saldo Arrastrado Mes Anterior", int(resumen.get("saldo_arrastrado") or 0)],
        ["Ingresos Extra / Abonos", int(resumen.get("total_ingresos_extra") or 0)],
        ["Capacidad Total del Mes", int(resumen.get("capacidad_total") or 0)],
        ["Meta de Ahorro Apartada", int(resumen.get("meta_ahorro") or 0)],
        ["Total Gastado en el Mes", int(resumen.get("total_gastado") or 0)],
        ["Saldo Disponible Final", int(resumen.get("saldo_disponible") or 0)],
        [
            "Presupuesto Diario Sugerido",
            int(resumen.get("presupuesto_diario_sugerido") or 0),
        ],
        ["", ""],
        ["RESUMEN POR CATEGORÍA", "TOTAL GASTADO (COP)"],
    ]

    gastos_cat: dict[str, int] = resumen.get("gastos_por_categoria", {})
    for cat, valor in gastos_cat.items():
        hoja_resumen.append([str(cat), int(valor)])

    hoja_movimientos: list[list[Any]] = [
        ["ID", "Fecha", "Tipo", "Concepto", "Categoría", "Sub-etiqueta", "Monto (COP)"]
    ]
    for ing in sorted(
        resumen.get("ingresos_extra", []), key=lambda x: int(x["id"])
    ):
        hoja_movimientos.append(
            [
                f"I-{ing['id']}",
                str(ing["fecha"]),
                "Ingreso Extra",
                str(ing["concepto"]),
                "Ingreso / Abono",
                "Liquidez",
                int(ing["monto"]),
            ]
        )

    for tx in sorted(
        resumen.get("transacciones", []), key=lambda x: int(x["id"])
    ):
        hoja_movimientos.append(
            [
                f"G-{tx['id']}",
                str(tx["fecha"]),
                "Gasto",
                str(tx["concepto"]),
                str(tx["categoria"]),
                str(tx.get("sub_etiqueta") or "General"),
                int(tx["monto"]),
            ]
        )

    hoja_compromisos: list[list[Any]] = [
        ["GASTOS FIJOS MENSUALES", "Categoría", "Valor Mensual (COP)", "Estado"],
    ]
    for gf in resumen.get("gastos_fijos", []):
        hoja_compromisos.append(
            [
                str(gf["nombre"]),
                str(gf["categoria"]),
                int(gf["monto"]),
                "Activo",
            ]
        )

    hoja_compromisos.extend(
        [
            ["", "", "", ""],
            [
                "CRÉDITOS Y OBLIGACIONES A CUOTAS",
                "Valor Cuota (COP)",
                "Progreso Cuotas",
                "Saldo Pendiente (COP)",
            ],
        ]
    )
    for cred in resumen.get("creditos", []):
        progreso = f"{cred['cuotas_pagadas']}/{cred['total_cuotas']}"
        hoja_compromisos.append(
            [
                str(cred["nombre"]),
                int(cred["valor_cuota"]),
                progreso,
                int(cred["saldo_pendiente"]),
            ]
        )

    return hoja_resumen, hoja_movimientos, hoja_compromisos


def _generar_xlsx_con_openpyxl(
    openpyxl_mod: Any,
    hojas: tuple[list[list[Any]], list[list[Any]], list[list[Any]]],
) -> bytes:
    """Construye el archivo `.xlsx` estilizado utilizando la librería `openpyxl`."""
    wb = openpyxl_mod.Workbook()
    styles = openpyxl_mod.styles
    utils = openpyxl_mod.utils

    fill_header = styles.PatternFill(
        start_color="1E293B", end_color="1E293B", fill_type="solid"
    )
    font_header = styles.Font(color="FFFFFF", bold=True)
    font_bold = styles.Font(bold=True)

    definiciones = [
        ("Resumen Mensual", hojas[0]),
        ("Movimientos", hojas[1]),
        ("Compromisos y Créditos", hojas[2]),
    ]

    for indice, (titulo, filas) in enumerate(definiciones):
        ws = wb.active if indice == 0 else wb.create_sheet(title=titulo)
        ws.title = titulo

        for fila in filas:
            ws.append(fila)

        for row_idx, row_cells in enumerate(ws.iter_rows(), start=1):
            Textos_encabezado = {
                "BOLSILLO v1.0 - REPORTE FINANCIERO MENSUAL",
                "INDICADOR GENERAL",
                "RESUMEN POR CATEGORÍA",
                "ID",
                "GASTOS FIJOS MENSUALES",
                "CRÉDITOS Y OBLIGACIONES A CUOTAS",
            }
            primer_valor = str(row_cells[0].value or "")
            es_encabezado = primer_valor in Textos_encabezado or row_idx == 1
            for cell in row_cells:
                if isinstance(cell.value, int):
                    cell.number_format = "$#,##0"
                if es_encabezado and cell.value not in (None, ""):
                    cell.fill = fill_header
                    cell.font = font_header
                elif row_idx <= 4 and indice == 0:
                    cell.font = font_bold

        if indice == 1 and len(filas) > 1:
            ws.auto_filter.ref = f"A1:G{len(filas)}"

        for col_idx, col_cells in enumerate(ws.columns, start=1):
            max_len = max(
                len(str(c.value or "")) for c in col_cells
            )
            col_letter = utils.get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 14)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _columna_excel(indice_base_1: int) -> str:
    """Convierte un índice de columna base 1 en letra de columna Excel (A, B, C...)."""
    resultado = ""
    num = indice_base_1
    while num > 0:
        num, resto = divmod(num - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _serializar_hoja_ooxml(filas: list[list[Any]], con_autofiltro: bool = False) -> str:
    """Genera el XML de una hoja `worksheet` estándar OpenXML (`.xlsx`)."""
    filas_xml: list[str] = []
    for r_idx, fila in enumerate(filas, start=1):
        celdas_xml: list[str] = []
        for c_idx, valor in enumerate(fila, start=1):
            ref = f"{_columna_excel(c_idx)}{r_idx}"
            if isinstance(valor, int) and not isinstance(valor, bool):
                celdas_xml.append(f'<c r="{ref}" s="1"><v>{valor}</v></c>')
            else:
                texto_seguro = escape(str(valor if valor is not None else ""))
                celdas_xml.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{texto_seguro}</t></is></c>'
                )
        filas_xml.append(f'<row r="{r_idx}">{"".join(celdas_xml)}</row>')

    bloque_filtro = (
        f'<autoFilter ref="A1:G{max(len(filas), 1)}"/>' if con_autofiltro else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(filas_xml)}</sheetData>'
        f"{bloque_filtro}"
        "</worksheet>"
    )


def _generar_xlsx_ooxml_nativo(
    hojas: tuple[list[list[Any]], list[list[Any]], list[list[Any]]],
) -> bytes:
    """Construye un archivo `.xlsx` OpenXML válido de 3 hojas usando `zipfile`."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet3.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels_raiz = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Resumen Mensual" sheetId="1" r:id="rId1"/>'
        '<sheet name="Movimientos" sheetId="2" r:id="rId2"/>'
        '<sheet name="Compromisos y Créditos" sheetId="3" r:id="rId3"/>'
        "</sheets></workbook>"
    )
    tipo_ws = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    )
    tipo_st = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{tipo_ws}" Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{tipo_ws}" Target="worksheets/sheet2.xml"/>'
        f'<Relationship Id="rId3" Type="{tipo_ws}" Target="worksheets/sheet3.xml"/>'
        f'<Relationship Id="rId4" Type="{tipo_st}" Target="styles.xml"/>'
        "</Relationships>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="$#,##0"/></numFmts>'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/></border></borders>'
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        "</cellStyleXfs>"
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" '
        'xfId="0" applyNumberFormat="1"/>'
        "</cellXfs></styleSheet>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_raiz)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", _serializar_hoja_ooxml(hojas[0]))
        zf.writestr(
            "xl/worksheets/sheet2.xml",
            _serializar_hoja_ooxml(hojas[1], con_autofiltro=True),
        )
        zf.writestr("xl/worksheets/sheet3.xml", _serializar_hoja_ooxml(hojas[2]))

    return buffer.getvalue()


def construir_archivo_excel_xlsx(
    resumen: dict[str, Any],
    nombre_usuario: str = "Espacio Personal",
) -> bytes:
    """Genera el contenido binario de un libro Excel (`.xlsx`) con 3 hojas.

    Args:
        resumen (dict[str, Any]): Estado financiero del periodo.
        nombre_usuario (str): Nombre del titular del reporte.

    Returns:
        bytes: Contenido binario del archivo `.xlsx`.
    """
    hojas = _construir_filas_hojas(resumen, nombre_usuario)
    try:
        import openpyxl  # pylint: disable=import-outside-toplevel

        return _generar_xlsx_con_openpyxl(openpyxl, hojas)
    except ImportError:
        return _generar_xlsx_ooxml_nativo(hojas)

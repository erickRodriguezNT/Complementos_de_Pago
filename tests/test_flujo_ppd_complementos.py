"""
Test suite: Factura PPD + 2 Complementos de Pago
===================================================
Execution order (pytest-ordering):
  test_01_factura_ppd         → genera CFDI FACTURA, guarda UUID
  test_02_complemento_pago_1  → primer pago parcial (usa UUID del test_01)
  test_03_complemento_pago_2  → segundo pago que liquida saldo (usa UUID del test_01 + saldo)

Run:  python run_tests.py
      OR: pytest tests/test_flujo_ppd_complementos.py -v -s
"""
import os
import pytest

from pages.factura_page import FacturaPage
from pages.complemento_pago_page import ComplementoPagoPage
from utils.excel_manager import ResultRow
from utils.logger import get_logger

log = get_logger("test_ppd_complementos")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 01 — Factura PPD
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_factura_ppd(logged_in_driver, config, conceptos_data, results_writer,
                         shared_state, screenshots_dir, downloads_dir):
    """Generate a CFDI FACTURA PPD and store the resulting UUID."""
    driver = logged_in_driver
    conceptos, impuestos = conceptos_data

    page = FacturaPage(driver)
    page.navigate(config["app"]["factura_url"])

    resultado = ResultRow(
        caso_prueba="FACTURA_PPD",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=config["emisor"]["rfc"],
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=config["emisor"]["sucursal"],
        centro_consumo=config["emisor"]["cc"],
    )

    try:
        # 1. Emisor
        page.fill_emisor(
            rfc=config["emisor"]["rfc"],
            sucursal=config["emisor"]["sucursal"],
            cc=config["emisor"]["cc"],
        )

        # 2. Receptor
        page.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )

        # 3. Comprobante
        page.fill_comprobante(
            tipo=config["comprobante"]["tipo"],
            serie=config["comprobante"]["serie"],
            forma_pago=config["comprobante"]["forma_pago"],
            metodo_pago=config["comprobante"]["metodo_pago"],
            moneda=config["comprobante"]["moneda"],
        )

        # 4. Conceptos
        page.add_all_conceptos(conceptos, impuestos)

        # 5. Screenshot before timbrar
        page.take_screenshot("before_timbrar_factura", screenshots_dir)

        # 6. Timbrar
        timbrado_timeout = int(config["timeouts"]["timbrado"])
        uuid_pagina = page.click_facturar(timeout=timbrado_timeout)
        log.info("UUID obtenido desde pantalla: %s", uuid_pagina or "(vacío)")

        # 7. Download CFDI ZIP
        zip_path, uuid_zip = page.click_descarga(downloads_dir)
        zip_filename = os.path.basename(zip_path)

        # UUID final: pantalla tiene prioridad; ZIP como fallback
        uuid = uuid_pagina or uuid_zip
        log.info("UUID final usado: %s", uuid or "(no encontrado)")

        # 8. Compute expected total (Subtotal + IVA)
        subtotal = sum(c.cantidad * c.valor_unitario for c in conceptos)
        iva = sum(
            c.cantidad * c.valor_unitario * i.tasa_cuota
            for c in conceptos
            for i in impuestos
            if i.id_concepto == c.id_concepto
        )
        total = round(subtotal + iva, 2)
        shared_state["uuid_factura"] = uuid
        shared_state["total_factura"] = total

        # Build datos_generales summary
        conceptos_summary = "; ".join(
            f"{c.descripcion} x{c.cantidad} @${c.valor_unitario}" for c in conceptos
        )
        resultado.datos_generales = (
            f"Subtotal: ${subtotal:.2f} | IVA: ${iva:.2f} | Total: ${total:.2f} | "
            f"Conceptos: {conceptos_summary}"
        )
        resultado.uuid_timbrado = uuid
        resultado.url_descarga_pdf = zip_filename
        resultado.resultado_obtenido = (
            f"PASS | UUID Timbrado: {uuid} | Archivo: {zip_filename}"
        )

        log.info("TEST_01 PASS — UUID=%s Total=$%.2f", uuid, total)

    except Exception as exc:
        page.take_screenshot("error_factura_ppd", screenshots_dir)
        resultado.resultado_obtenido = f"FAIL: {exc}"
        log.error("TEST_01 FAIL: %s", exc)
        results_writer.add_row(resultado)
        pytest.fail(str(exc))

    results_writer.add_row(resultado)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 02 — Complemento de Pago 1 (parcial)
# ═══════════════════════════════════════════════════════════════════════════════

def test_02_complemento_pago_1(logged_in_driver, config, pagos_data, results_writer,
                                shared_state, screenshots_dir, downloads_dir):
    """Generate first Complemento de Pago (partial payment) using Excel pagos data."""
    driver = logged_in_driver
    uuid_factura = shared_state.get("uuid_factura")
    total_factura = shared_state.get("total_factura", 0.0)

    if not uuid_factura:
        pytest.skip("UUID Factura not available — test_01 may have failed")

    monto_pago1 = pagos_data.cp1
    saldo_insoluto = max(0.0, round(total_factura - monto_pago1, 2))
    shared_state["saldo_insoluto_comp1"] = saldo_insoluto

    page = ComplementoPagoPage(driver)
    page.navigate(config["app"]["factura_url"])

    resultado = ResultRow(
        caso_prueba="COMPLEMENTO_PAGO_1",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=config["emisor"]["rfc"],
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=config["emisor"]["sucursal"],
        centro_consumo=config["emisor"]["cc"],
        uuid_relacionado=uuid_factura,
    )

    try:
        # 1. Emisor
        page.fill_emisor(
            rfc=config["emisor"]["rfc"],
            sucursal=config["emisor"]["sucursal"],
            cc=config["emisor"]["cc"],
        )

        # 2. Receptor
        page.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )

        # 3. Tipo = PAGO, Serie = CP
        page.fill_comprobante_cp_basico(tipo="PAGO", serie="CP")

        # 4. Fecha de Pago
        page.fill_fecha_pago(pagos_data.fecha_pago)

        # 5. Forma de Pago
        page.fill_forma_pago_complemento(pagos_data.forma_pago)

        # 6. Moneda de Pago
        page.fill_moneda_pago_complemento(pagos_data.moneda_pago)

        # 7–12. DR flow: abrir panel → buscar CFDI → importe → agregar → cerrar → agregar pago
        page.flujo_dr_completo(
            uuid_factura=uuid_factura,
            importe_pago=f"{monto_pago1:.2f}",
            emisor_rfc=config["emisor"]["rfc"],
            sucursal=config["emisor"]["sucursal"],
            cc=config["emisor"]["cc"],
        )

        # 13. Screenshot before timbrar
        page.take_screenshot("before_timbrar_comp1", screenshots_dir)

        # 14. Timbrar
        timbrado_timeout = int(config["timeouts"]["timbrado"])
        uuid_comp1 = page.timbrar_complemento(timeout=timbrado_timeout)

        # 15. Download ZIP
        zip_path, uuid_zip = page.click_descarga(downloads_dir)
        zip_filename = os.path.basename(zip_path)

        shared_state["uuid_comp1"] = uuid_comp1
        resultado.datos_generales = (
            f"Parcialidad: 1 | Monto: ${monto_pago1:.2f} | "
            f"Forma Pago: {pagos_data.forma_pago} | Moneda: {pagos_data.moneda_pago} | "
            f"Fecha: {pagos_data.fecha_pago} | "
            f"Saldo Anterior: ${total_factura:.2f} | Saldo Insoluto: ${saldo_insoluto:.2f}"
        )
        resultado.uuid_timbrado = uuid_comp1
        resultado.url_descarga_pdf = zip_filename
        resultado.resultado_obtenido = (
            f"PASS | UUID Comp.1: {uuid_comp1} | "
            f"Factura Relacionada: {uuid_factura} | Archivo: {zip_filename}"
        )

        log.info(
            "TEST_02 PASS — UUID_COMP1=%s  Saldo Insoluto=$%.2f",
            uuid_comp1, saldo_insoluto,
        )

    except Exception as exc:
        page.take_screenshot("error_complemento_pago_1", screenshots_dir)
        resultado.resultado_obtenido = f"FAIL: {exc}"
        log.error("TEST_02 FAIL: %s", exc)
        results_writer.add_row(resultado)
        pytest.fail(str(exc))

    results_writer.add_row(resultado)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 03 — Complemento de Pago 2 (liquida saldo)
# ═══════════════════════════════════════════════════════════════════════════════

def test_03_complemento_pago_2(logged_in_driver, config, pagos_data, results_writer,
                                shared_state, screenshots_dir, downloads_dir):
    """Generate second Complemento de Pago using CP2 value from Excel pagos sheet."""
    driver = logged_in_driver
    uuid_factura = shared_state.get("uuid_factura")

    if not uuid_factura:
        pytest.skip("UUID Factura not available — test_01 may have failed")

    monto_pago2 = pagos_data.cp2
    saldo_anterior = shared_state.get("saldo_insoluto_comp1", 0.0)
    saldo_insoluto = max(0.0, round(saldo_anterior - monto_pago2, 2))
    shared_state["saldo_insoluto_comp2"] = saldo_insoluto

    page = ComplementoPagoPage(driver)
    page.navigate(config["app"]["factura_url"])

    resultado = ResultRow(
        caso_prueba="COMPLEMENTO_PAGO_2",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=config["emisor"]["rfc"],
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=config["emisor"]["sucursal"],
        centro_consumo=config["emisor"]["cc"],
        uuid_relacionado=uuid_factura,
    )

    try:
        # 1. Emisor
        page.fill_emisor(
            rfc=config["emisor"]["rfc"],
            sucursal=config["emisor"]["sucursal"],
            cc=config["emisor"]["cc"],
        )

        # 2. Receptor
        page.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )

        # 3. Tipo = PAGO, Serie = CP
        page.fill_comprobante_cp_basico(tipo="PAGO", serie="CP")

        # 4. Fecha de Pago
        page.fill_fecha_pago(pagos_data.fecha_pago)

        # 5. Forma de Pago
        page.fill_forma_pago_complemento(pagos_data.forma_pago)

        # 6. Moneda de Pago
        page.fill_moneda_pago_complemento(pagos_data.moneda_pago)

        # 7–12. DR flow: abrir panel → buscar CFDI → importe → agregar → cerrar → agregar pago
        page.flujo_dr_completo(
            uuid_factura=uuid_factura,
            importe_pago=f"{monto_pago2:.2f}",
            emisor_rfc=config["emisor"]["rfc"],
            sucursal=config["emisor"]["sucursal"],
            cc=config["emisor"]["cc"],
        )

        # 13. Screenshot before timbrar
        page.take_screenshot("before_timbrar_comp2", screenshots_dir)

        # 14. Timbrar
        timbrado_timeout = int(config["timeouts"]["timbrado"])
        uuid_comp2 = page.timbrar_complemento(timeout=timbrado_timeout)

        # 15. Download ZIP
        zip_path, uuid_zip = page.click_descarga(downloads_dir)
        zip_filename = os.path.basename(zip_path)

        shared_state["uuid_comp2"] = uuid_comp2
        resultado.datos_generales = (
            f"Parcialidad: 2 | Monto: ${monto_pago2:.2f} | "
            f"Forma Pago: {pagos_data.forma_pago} | Moneda: {pagos_data.moneda_pago} | "
            f"Fecha: {pagos_data.fecha_pago} | "
            f"Saldo Anterior: ${saldo_anterior:.2f} | Saldo Insoluto: ${saldo_insoluto:.2f}"
        )
        resultado.uuid_timbrado = uuid_comp2
        resultado.url_descarga_pdf = zip_filename
        resultado.resultado_obtenido = (
            f"PASS | UUID Comp.2: {uuid_comp2} | "
            f"Factura Relacionada: {uuid_factura} | Archivo: {zip_filename}"
        )

        log.info(
            "TEST_03 PASS — UUID_COMP2=%s  Saldo Insoluto=$%.2f",
            uuid_comp2, saldo_insoluto,
        )

    except Exception as exc:
        page.take_screenshot("error_complemento_pago_2", screenshots_dir)
        resultado.resultado_obtenido = f"FAIL: {exc}"
        log.error("TEST_03 FAIL: %s", exc)
        results_writer.add_row(resultado)
        pytest.fail(str(exc))

    results_writer.add_row(resultado)

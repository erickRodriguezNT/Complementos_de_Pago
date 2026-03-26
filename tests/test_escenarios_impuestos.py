"""
Test suite: Ciclo completo PPD + Complementos de Pago por Escenario
=====================================================================
Por cada escenario definido en el Excel se ejecuta el flujo completo:

  PASO 1 — Factura PPD  (con los conceptos e impuestos del escenario)
  PASO 2 — Complemento de Pago 1  (monto CP1 del Excel, parcialidad 1)
  PASO 3 — Complemento de Pago 2  (monto CP2 del Excel, liquida saldo)

Pytest genera automáticamente un test independiente por cada escenario
definido en la hoja 'escenarios' del Excel (via pytest_generate_tests en
conftest.py).  Los 3 pasos de cada escenario son LOCALES entre sí — no
comparten estado con otros escenarios.

Ejecución:
  pytest tests/test_escenarios_impuestos.py -v -s
  pytest tests/test_escenarios_impuestos.py -v -s -k "esc3"
  pytest tests/test_escenarios_impuestos.py -v -s -k "esc1 or esc2"
"""
from __future__ import annotations

import os
import pytest

from pages.factura_page import FacturaPage
from pages.complemento_pago_page import ComplementoPagoPage
from utils.excel_manager import EscenarioData, ResultRow, get_pago_by_escenario
from utils.logger import get_logger, log_section, log_step

log = get_logger("test_escenarios_impuestos")


# ═══════════════════════════════════════════════════════════════════════════════
# ÚNICO TEST — parametrizado automáticamente desde el Excel
# Cada instancia ejecuta el ciclo completo: PPD → CP1 → CP2
# ═══════════════════════════════════════════════════════════════════════════════

def test_flujo_completo_escenario(
    logged_in_driver,
    config,
    escenario,      # EscenarioData | None — inyectado por pytest_generate_tests
    pagos_data,
    results_writer,
    escenario_dir,
):
    """Ciclo completo PPD + CP1 + CP2 para el escenario de impuestos del Excel.

    Los 3 pasos son independientes por escenario — no comparten estado con
    otros escenarios.  Si el PASO 1 falla el test se detiene para ese
    escenario; los demás escenarios siguen ejecutándose normalmente.
    """
    if escenario is None:
        pytest.skip("No se encontraron escenarios en el Excel")

    assert isinstance(escenario, EscenarioData), \
        f"Fixture 'escenario' debe ser EscenarioData, got {type(escenario)}"

    driver = logged_in_driver
    esc_id = escenario.id_escenario
    esc_name = escenario.nombre
    timbrado_timeout = int(config["timeouts"]["timbrado"])
    esc_rfc, esc_suc, esc_cc = _get_emisor(escenario, config)
    pago = get_pago_by_escenario(pagos_data, esc_id)

    log_section(log, f"ESCENARIO {esc_id:02d} — {esc_name}")
    log.info("  Emisor: %s | Sucursal: %s | CC: %s", esc_rfc, esc_suc, esc_cc)
    log.info("  Pago: fecha=%s | forma=%s | moneda=%s | CP1=%.2f | CP2=%.2f",
             pago.fecha_pago, pago.forma_pago, pago.moneda_pago, pago.cp1, pago.cp2)
    if escenario.moneda_ppd:
        log.info("  PPD moneda override: %s", escenario.moneda_ppd)
    log.info(
        "  Conceptos: %d | Impuestos: %d",
        len(escenario.conceptos), len(escenario.impuestos),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 1 — Factura PPD
    # ─────────────────────────────────────────────────────────────────────────
    log_step(log, 1, "Factura PPD")
    res_ppd = ResultRow(
        caso_prueba=f"ESC{esc_id}_PPD — {esc_name}",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=esc_rfc,
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=esc_suc,
        centro_consumo=esc_cc,
        datos_generales=(
            f"Escenario {esc_id}: {esc_name} | "
            f"Impuestos: {', '.join(_describe_impuesto(i) for i in escenario.impuestos)}"
        ),
    )

    uuid_factura = None
    total_factura = 0.0

    fac_page = FacturaPage(driver)
    try:
        fac_page.navigate(config["app"]["factura_url"])

        fac_page.fill_emisor(
            rfc=esc_rfc,
            sucursal=esc_suc,
            cc=esc_cc,
        )
        fac_page.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )
        fac_page.fill_comprobante(
            tipo=config["comprobante"]["tipo"],
            serie=_resolve_serie(esc_rfc, config["comprobante"]["serie"]),
            forma_pago=config["comprobante"]["forma_pago"],
            metodo_pago=config["comprobante"]["metodo_pago"],
            moneda=escenario.moneda_ppd or config["comprobante"]["moneda"],
            tipo_cambio=pago.tipo_cambio_pago if escenario.moneda_ppd else 0.0,
        )
        fac_page.add_all_conceptos(escenario.conceptos, escenario.impuestos)
        fac_page.take_screenshot(f"before_timbrar_esc{esc_id}_ppd", escenario_dir)

        uuid_pagina = fac_page.click_facturar(timeout=timbrado_timeout)
        _set_download_dir(driver, escenario_dir)
        zip_path, uuid_zip = fac_page.click_descarga(escenario_dir)
        zip_filename = os.path.basename(zip_path)

        uuid_factura = uuid_pagina or uuid_zip

        # Calcular total (subtotal + impuestos traslado)
        subtotal = sum(c.cantidad * c.valor_unitario for c in escenario.conceptos)
        impuestos_traslado = [
            i for i in escenario.impuestos
            if "traslado" in i.retencion_traslado.lower()
        ]
        iva = sum(
            c.cantidad * c.valor_unitario * i.tasa_cuota
            for c in escenario.conceptos
            for i in impuestos_traslado
            if i.id_concepto == c.id_concepto
        )
        total_factura = round(subtotal + iva, 2)

        res_ppd.uuid_timbrado = uuid_factura or ""
        res_ppd.url_descarga_pdf = zip_filename
        res_ppd.resultado_obtenido = (
            f"PASS | UUID: {uuid_factura} | "
            f"Subtotal: ${subtotal:.2f} | Total: ${total_factura:.2f} | "
            f"Archivo: {zip_filename}"
        )
        log_step(log, 1, f"Factura PPD — ESC{esc_id} UUID={uuid_factura} Total=${total_factura:.2f}", status="PASS")

    except Exception as exc:
        fac_page.take_screenshot(f"error_esc{esc_id}_ppd", escenario_dir)
        res_ppd.resultado_obtenido = f"FAIL: {exc}"
        log.error("PASO 1 FAIL ESC%d: %s", esc_id, exc)
        results_writer.add_row(res_ppd)
        pytest.fail(str(exc))

    results_writer.add_row(res_ppd)

    if not uuid_factura:
        pytest.fail(f"ESC{esc_id}: No se obtuvo UUID de la factura PPD")

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 2 — Complemento de Pago 1
    # ─────────────────────────────────────────────────────────────────────────
    log_step(log, 2, "Complemento de Pago 1")
    monto_cp1 = pago.cp1
    saldo_insoluto_cp1 = max(0.0, round(total_factura - monto_cp1, 2))

    res_cp1 = ResultRow(
        caso_prueba=f"ESC{esc_id}_CP1 — {esc_name}",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=esc_rfc,
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=esc_suc,
        centro_consumo=esc_cc,
        uuid_relacionado=uuid_factura,
        datos_generales=(
            f"Parcialidad: 1 | Monto: ${monto_cp1:.2f} | "
            f"Saldo Anterior: ${total_factura:.2f} | Saldo Insoluto: ${saldo_insoluto_cp1:.2f}"
        ),
    )

    uuid_comp1 = None
    cp_page = ComplementoPagoPage(driver)
    try:
        cp_page.navigate(config["app"]["factura_url"])

        cp_page.fill_emisor(
            rfc=esc_rfc,
            sucursal=esc_suc,
            cc=esc_cc,
        )
        cp_page.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )
        cp_page.fill_comprobante_cp_basico(tipo="PAGO", serie="CP")
        cp_page.fill_fecha_pago(pago.fecha_pago)
        cp_page.fill_forma_pago_complemento(pago.forma_pago)
        cp_page.fill_moneda_pago_complemento(pago.moneda_pago)
        if pago.tipo_cambio_pago > 0:
            cp_page.fill_tipo_cambio_pago(pago.tipo_cambio_pago)
        cp_page.flujo_dr_completo(
            uuid_factura=uuid_factura,
            importe_pago=f"{monto_cp1:.2f}",
            emisor_rfc=esc_rfc,
            sucursal=esc_suc,
            cc=esc_cc,
            equivalencia_dr=pago.equivalencia_dr,
        )
        cp_page.take_screenshot(f"before_timbrar_esc{esc_id}_cp1", escenario_dir)

        uuid_comp1 = cp_page.timbrar_complemento(timeout=timbrado_timeout)
        _set_download_dir(driver, escenario_dir)
        zip_path, uuid_zip = cp_page.click_descarga(escenario_dir)
        zip_filename = os.path.basename(zip_path)

        res_cp1.uuid_timbrado = uuid_comp1 or ""
        res_cp1.url_descarga_pdf = zip_filename
        res_cp1.resultado_obtenido = (
            f"PASS | UUID Comp.1: {uuid_comp1} | "
            f"Factura Relacionada: {uuid_factura} | Archivo: {zip_filename}"
        )
        log_step(log, 2, f"Complemento de Pago 1 — ESC{esc_id} UUID={uuid_comp1}", status="PASS")

    except Exception as exc:
        cp_page.take_screenshot(f"error_esc{esc_id}_cp1", escenario_dir)
        res_cp1.resultado_obtenido = f"FAIL: {exc}"
        log.error("PASO 2 FAIL ESC%d: %s", esc_id, exc)
        results_writer.add_row(res_cp1)
        pytest.fail(str(exc))

    results_writer.add_row(res_cp1)

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 3 — Complemento de Pago 2
    # ─────────────────────────────────────────────────────────────────────────
    log_step(log, 3, "Complemento de Pago 2")
    monto_cp2 = pago.cp2
    saldo_insoluto_cp2 = max(0.0, round(saldo_insoluto_cp1 - monto_cp2, 2))

    res_cp2 = ResultRow(
        caso_prueba=f"ESC{esc_id}_CP2 — {esc_name}",
        resultado_esperado="Timbrado exitoso - UUID generado",
        rfc_emisor=esc_rfc,
        rfc_receptor=config["receptor"]["rfc"],
        sucursal=esc_suc,
        centro_consumo=esc_cc,
        uuid_relacionado=uuid_factura,
        datos_generales=(
            f"Parcialidad: 2 | Monto: ${monto_cp2:.2f} | "
            f"Saldo Anterior: ${saldo_insoluto_cp1:.2f} | Saldo Insoluto: ${saldo_insoluto_cp2:.2f}"
        ),
    )

    cp_page2 = ComplementoPagoPage(driver)
    try:
        cp_page2.navigate(config["app"]["factura_url"])

        cp_page2.fill_emisor(
            rfc=esc_rfc,
            sucursal=esc_suc,
            cc=esc_cc,
        )
        cp_page2.fill_receptor(
            rfc=config["receptor"]["rfc"],
            nombre="PUBLICO EN GENERAL",
            uso_cfdi=config["receptor"]["uso_cfdi"],
            regimen=config["receptor"]["regimen"],
            domicilio_cp=config["receptor"]["domicilio_cp"],
            email=config["receptor"]["email"],
        )
        cp_page2.fill_comprobante_cp_basico(tipo="PAGO", serie="CP")
        cp_page2.fill_fecha_pago(pago.fecha_pago)
        cp_page2.fill_forma_pago_complemento(pago.forma_pago)
        cp_page2.fill_moneda_pago_complemento(pago.moneda_pago)
        if pago.tipo_cambio_pago > 0:
            cp_page2.fill_tipo_cambio_pago(pago.tipo_cambio_pago)
        cp_page2.flujo_dr_completo(
            uuid_factura=uuid_factura,
            importe_pago=f"{monto_cp2:.2f}",
            emisor_rfc=esc_rfc,
            sucursal=esc_suc,
            cc=esc_cc,
            equivalencia_dr=pago.equivalencia_dr,
        )
        cp_page2.take_screenshot(f"before_timbrar_esc{esc_id}_cp2", escenario_dir)

        uuid_comp2 = cp_page2.timbrar_complemento(timeout=timbrado_timeout)
        _set_download_dir(driver, escenario_dir)
        zip_path, uuid_zip = cp_page2.click_descarga(escenario_dir)
        zip_filename = os.path.basename(zip_path)

        res_cp2.uuid_timbrado = uuid_comp2 or ""
        res_cp2.url_descarga_pdf = zip_filename
        res_cp2.resultado_obtenido = (
            f"PASS | UUID Comp.2: {uuid_comp2} | "
            f"Factura Relacionada: {uuid_factura} | Archivo: {zip_filename}"
        )
        log_step(log, 3, f"Complemento de Pago 2 — ESC{esc_id} UUID={uuid_comp2} Saldo=${saldo_insoluto_cp2:.2f}", status="PASS")

    except Exception as exc:
        cp_page2.take_screenshot(f"error_esc{esc_id}_cp2", escenario_dir)
        res_cp2.resultado_obtenido = f"FAIL: {exc}"
        log.error("PASO 3 FAIL ESC%d: %s", esc_id, exc)
        results_writer.add_row(res_cp2)
        pytest.fail(str(exc))

    results_writer.add_row(res_cp2)

    log_section(log, f"ESCENARIO {esc_id:02d} — {esc_name}", status="PASS")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _set_download_dir(driver, directory: str) -> None:
    """Redirige el directorio de descarga de Chrome vía CDP (sin reiniciar el driver)."""
    try:
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": os.path.abspath(directory),
            "eventsEnabled": True,
        })
    except Exception:
        pass


def _get_emisor(escenario, config) -> tuple:
    """Devuelve (rfc, sucursal, cc) del escenario si están definidos en el Excel,
    o los valores de [emisor] en config.ini como fallback."""
    if escenario and escenario.rfc_emisor:
        return escenario.rfc_emisor, escenario.sucursal, escenario.cc
    return (
        config["emisor"]["rfc"],
        config["emisor"]["sucursal"],
        config["emisor"]["cc"],
    )


# RFC → serie forzada. Agregar aquí nuevas reglas sin tocar el test.
_SERIE_POR_EMISOR = {
    "TPA110608SW9": "F",
}


def _resolve_serie(rfc_emisor: str, serie_default: str) -> str:
    """Devuelve la serie correcta según el RFC del emisor.

    Si el emisor tiene una serie forzada definida en _SERIE_POR_EMISOR la usa;
    de lo contrario respeta la serie que viene de config.ini.
    """
    forzada = _SERIE_POR_EMISOR.get(rfc_emisor)
    if forzada:
        log.info("Serie forzada a '%s' para emisor %s", forzada, rfc_emisor)
        return forzada
    return serie_default


def _describe_impuesto(imp) -> str:
    """Breve descripción legible de un ImpuestoRow para logs y reportes."""
    tasa_str = f"{imp.tasa_cuota:.0%}" if imp.tasa_cuota else "exento"
    return f"{imp.clave_impuesto} {tasa_str} ({imp.retencion_traslado})"

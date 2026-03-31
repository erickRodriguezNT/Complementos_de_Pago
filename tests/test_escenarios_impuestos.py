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
from utils.excel_manager import EscenarioData, ResultRow, get_pago_by_escenario, get_active_cp_values
from utils.logger import get_logger, log_section, log_step

log = get_logger("test_escenarios_impuestos")


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# Único TEST — parametrizado automáticamente desde el Excel
# Cada instancia ejecuta el ciclo completo: PPD → CP1 → CP2 → ... → CPn
# ═══════════════════════════════════════════════════════════════════════════════

def test_flujo_completo_escenario(
    logged_in_driver,
    config,
    escenario,      # EscenarioData | None — inyectado por pytest_generate_tests
    pagos_data,
    results_writer,
    escenario_dir,
):
    """Ciclo completo PPD + CPs dinámicos para el escenario de impuestos del Excel.

    Todos los pasos son independientes por escenario — no comparten estado con
    otros escenarios.  Si el PASO 1 falla el test se detiene para ese
    escenario; los demás escenarios siguen ejecutándose normalmente.
    Los complementos de pago se ejecutan solo si hay columnas CP con valor > 0.
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
    _cp_summary = " | ".join(
        f"CP{i + 1}={v:.2f}" for i, v in enumerate(pago.cp_values)
    ) or "sin CP"
    log.info("  Pago: fecha=%s | forma=%s | moneda=%s | %s",
             pago.fecha_pago, pago.forma_pago, pago.moneda_pago, _cp_summary)
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
    # PASOS 2..N — Complementos de Pago (dinámico: CP1, CP2, ..., CPn)
    # Se ejecuta un paso por cada columna CPn que tenga valor > 0 en el Excel.
    # Si ninguna columna CP tiene valor, se omite el flujo de Complemento.
    # ─────────────────────────────────────────────────────────────────────────
    active_cps = get_active_cp_values(pago)

    if not active_cps:
        log.info("ESC%d: Sin complementos de pago configurados — solo se ejecuta PPD", esc_id)
    else:
        saldo = total_factura
        for cp_idx, monto_cp in enumerate(active_cps, start=1):
            log_step(log, cp_idx + 1, f"Complemento de Pago {cp_idx}")
            saldo_anterior = saldo
            saldo = max(0.0, round(saldo - monto_cp, 2))

            res_cp = ResultRow(
                caso_prueba=f"ESC{esc_id}_CP{cp_idx} — {esc_name}",
                resultado_esperado="Timbrado exitoso - UUID generado",
                rfc_emisor=esc_rfc,
                rfc_receptor=config["receptor"]["rfc"],
                sucursal=esc_suc,
                centro_consumo=esc_cc,
                uuid_relacionado=uuid_factura,
                datos_generales=(
                    f"Parcialidad: {cp_idx} | Monto: ${monto_cp:.2f} | "
                    f"Saldo Anterior: ${saldo_anterior:.2f} | Saldo Insoluto: ${saldo:.2f}"
                ),
            )

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
                    importe_pago=f"{monto_cp:.2f}",
                    emisor_rfc=esc_rfc,
                    sucursal=esc_suc,
                    cc=esc_cc,
                    equivalencia_dr=pago.equivalencia_dr,
                )

                # Leer valores reales calculados por el sistema desde la UI
                datos_dr = cp_page.read_datos_dr_row()
                if datos_dr["saldo_anterior"] > 0 or datos_dr["saldo_insoluto"] > 0:
                    saldo = datos_dr["saldo_insoluto"]
                    res_cp.datos_generales = (
                        f"Parcialidad: {cp_idx} | "
                        f"Monto {pago.moneda_pago}: {monto_cp:.2f} | "
                        f"Pago (moneda factura): ${datos_dr['pago']:.2f} | "
                        f"Saldo Anterior: ${datos_dr['saldo_anterior']:.2f} | "
                        f"Saldo Insoluto: ${datos_dr['saldo_insoluto']:.2f}"
                    )
                    log.info(
                        "ESC%d CP%d: UI → Saldo Anterior=%.2f | Pago=%.2f | Saldo Insoluto=%.2f",
                        esc_id, cp_idx,
                        datos_dr["saldo_anterior"], datos_dr["pago"], datos_dr["saldo_insoluto"],
                    )
                else:
                    log.warning(
                        "ESC%d CP%d: tableDocRelacionado vacío — usando cálculo local "
                        "(moneda pago=%s, monto=%.2f)",
                        esc_id, cp_idx, pago.moneda_pago, monto_cp,
                    )

                cp_page.take_screenshot(
                    f"before_timbrar_esc{esc_id}_cp{cp_idx}", escenario_dir
                )

                uuid_cp = cp_page.timbrar_complemento(timeout=timbrado_timeout)
                _set_download_dir(driver, escenario_dir)
                zip_path, uuid_zip = cp_page.click_descarga(escenario_dir)
                zip_filename = os.path.basename(zip_path)

                res_cp.uuid_timbrado = uuid_cp or ""
                res_cp.url_descarga_pdf = zip_filename
                res_cp.resultado_obtenido = (
                    f"PASS | UUID CP{cp_idx}: {uuid_cp} | "
                    f"Factura Relacionada: {uuid_factura} | Archivo: {zip_filename}"
                )
                log_step(
                    log, cp_idx + 1,
                    f"CP{cp_idx} — ESC{esc_id} UUID={uuid_cp} Saldo=${saldo:.2f}",
                    status="PASS",
                )

            except Exception as exc:
                cp_page.take_screenshot(
                    f"error_esc{esc_id}_cp{cp_idx}", escenario_dir
                )
                res_cp.resultado_obtenido = f"FAIL: {exc}"
                log.error("PASO %d FAIL ESC%d (CP%d): %s", cp_idx + 1, esc_id, cp_idx, exc)
                results_writer.add_row(res_cp)
                pytest.fail(str(exc))

            results_writer.add_row(res_cp)

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

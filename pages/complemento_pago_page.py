"""Complemento de Pago Page Object.

Reuses the same factura_manual_40.xhtml page.
Flow:
  1. fill_emisor / fill_receptor
  2. fill_comprobante_cp_basico (PAGO + CP)
  3. fill_fecha_pago
  4. fill_forma_pago_complemento
  5. fill_moneda_pago_complemento
  6. flujo_dr_completo(uuid_factura, importe)   ← orchestrates steps 7-12
  7. timbrar_complemento / click_descarga
"""
from __future__ import annotations

from datetime import datetime

from selenium.webdriver.common.by import By

from pages.factura_page import (
    FacturaPage,
    _SERIE,
    _TIPO_COMPROBANTE,
    _BTN_DESCARGA, _BTN_DESCARGA_CSS,  # re-export for callers
)
from utils.waits import (
    wait_for_ajax,
    wait_for_element_clickable,
    wait_for_element_visible,
)
from utils.logger import get_logger

log = get_logger("complemento_pago_page")

# ── Pago comprobante header ──────────────────────────────────────────────────
_FECHA_PAGO_BTN_CSS = (
    r"#formNuevaFactura\:accordionDatosComprobante\:fechaPago > button"
)
_FORMA_PAGO_PAGOP   = "formNuevaFactura:accordionDatosComprobante:selectOneFormaPagoP"
_MONEDA_PAGO_P_AC   = "formNuevaFactura:accordionDatosComprobante:autoCompleteMonedaP_input"

# ── "Documento Relacionado (DR)" section button → opens j_idt293 via AJAX ───
_BTN_DR_SECTION     = "formNuevaFactura:accordionDatosComprobante:j_idt417"

# ── j_idt293 dialog ("Documento Relacionado") ───────────────────────────────
_DIALOG_DR_ID        = "formNuevaFactura:accordionDatosComprobante:j_idt293"
_DIALOG_DR_CLOSE_CSS = (
    r"#formNuevaFactura\:accordionDatosComprobante\:j_idt293 a.ui-dialog-titlebar-close"
)
_BTN_BUSCAR_EN_DR    = "formNuevaFactura:accordionDatosComprobante:j_idt351"
_BTN_AGREGAR_EN_DR   = "formNuevaFactura:accordionDatosComprobante:j_idt350"
_IMPORTE_PAGO_INPUT  = (
    "formNuevaFactura:accordionDatosComprobante:importePagoRelacionadoComplemento_input"
)

# ── dialogDocRelacionado ("Búsqueda de CFDI") ───────────────────────────────
_DIALOG_BUSQUEDA_ID       = "formNuevaFactura:dialogDocRelacionado"
_UUID_BUSQUEDA_INPUT      = "formNuevaFactura:inputUuidBusquedaDocRel"
_BTN_BUSCAR_CFDI          = "formNuevaFactura:j_idt1804"
_BTN_AGREGAR_RESULT_0_CSS = (
    r"#formNuevaFactura\:dataTableBusquedaDocRelacionado\:0\:j_idt1819"
)

# ── "Agregar pago" button in main form ──────────────────────────────────────
_BTN_AGREGAR_PAGO = "formNuevaFactura:accordionDatosComprobante:j_idt418"
# ── dialogDocRelacionado filter dropdowns ─────────────────────────────────────
_EMISOR_DR_SEARCH  = "formNuevaFactura:selectOneEmisorDocRel"
_SUCURS_DR_SEARCH  = "formNuevaFactura:selectOneSucursDocRel"
_CC_DR_SEARCH      = "formNuevaFactura:selectOneCentroConsumoDocRel"
# ── jQuery-UI Datepicker CSS (single shared overlay) ───────────────────────
_DP_CONTAINER  = "#ui-datepicker-div"
_DP_TITLE      = "#ui-datepicker-div .ui-datepicker-title"
_DP_NEXT       = "#ui-datepicker-div .ui-datepicker-next"
_DP_PREV       = "#ui-datepicker-div .ui-datepicker-prev"
_DP_DAY_XPATH  = (
    "//div[@id='ui-datepicker-div']"
    "//td[@data-handler='selectDay' and not(contains(@class,'ui-datepicker-other-month'))]"
    "//a[normalize-space(text())='{day}']"
)

_ES_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


class ComplementoPagoPage(FacturaPage):
    """Extends FacturaPage with Complemento de Pago (CP) specific steps."""

    # ── Comprobante basics ───────────────────────────────────────────────────

    def set_tipo_pago(self):
        """Change Tipo Comprobante dropdown to PAGO."""
        log.info("set_tipo_pago")
        self.select_one_menu_contains(_TIPO_COMPROBANTE, "PAGO")

    def fill_comprobante_cp_basico(self, tipo: str = "PAGO", serie: str = "CP"):
        """Set Tipo = PAGO and Serie = CP (no Forma/Método fields for CP type).

        Uses jQuery trigger('change') on the hidden PrimeFaces <select> to fire
        the onchange AJAX handler reliably, avoiding the double-click toggle issue
        that affects the visual trigger approach on some page states.
        """
        import time as _time
        log.info("fill_comprobante_cp_basico: tipo=%s serie=%s", tipo, serie)

        # Let any prior AJAX (e.g. receptor autofill accordion re-render) settle
        wait_for_ajax(self.driver)
        _time.sleep(0.5)

        # Set value on hidden <select> and fire jQuery change → PrimeFaces AJAX
        input_id = _TIPO_COMPROBANTE + "_input"
        self.driver.execute_script(
            "var el = document.getElementById(arguments[0]);"
            "el.value = arguments[1];"
            "window.jQuery(el).trigger('change');",
            input_id, tipo,
        )
        wait_for_ajax(self.driver)

        # Verify the visible _label was updated (server or client-side)
        label_id = _TIPO_COMPROBANTE + "_label"
        try:
            label_text = self.driver.find_element(By.ID, label_id).text.strip()
            if tipo.lower() not in label_text.lower():
                log.warning(
                    "Tipo label shows '%s' after jQuery trigger — falling back to UI click",
                    label_text,
                )
                self._select_tipo_comprobante(tipo)
                wait_for_ajax(self.driver)
            else:
                log.info("Tipo Comprobante set to: %s", label_text)
        except Exception:
            log.warning("Could not verify Tipo label — continuing")

        # Update local visible label if PrimeFaces client-side didn't do it
        self.driver.execute_script(
            "try { document.getElementById(arguments[0]).textContent = arguments[1]; } catch(e) {}",
            label_id, tipo,
        )

        # Serie — click the widget to open the dropdown, then click the matching
        # li item via JavaScript (avoids waiting for panel visibility which is
        # unreliable inside panelComplementoPago after PAGO AJAX re-render).
        wait_for_ajax(self.driver)
        _time.sleep(0.3)
        log.info("Serie: opening dropdown to select '%s'", serie)
        try:
            trigger = wait_for_element_clickable(self.driver, By.ID, _SERIE, timeout=10)
            self.scroll_to(trigger)
            try:
                trigger.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", trigger)
            _time.sleep(0.4)

            result = self.driver.execute_script(
                "var panel = document.getElementById(arguments[0] + '_panel');"
                "if (!panel) return 'no_panel';"
                "var items = panel.querySelectorAll('li.ui-selectonemenu-item');"
                "for (var i = 0; i < items.length; i++) {"
                "  var lbl = (items[i].getAttribute('data-label')"
                "    || items[i].textContent || '').trim();"
                "  if (lbl.toLowerCase() === arguments[1].toLowerCase()) {"
                "    items[i].click();"
                "    return 'clicked:' + lbl;"
                "  }"
                "}"
                "return 'not_found:' + items.length;",
                _SERIE, serie,
            )
            log.info("Serie click result: %s", result)
            if result and result.startswith("clicked:"):
                wait_for_ajax(self.driver)
                log.info("Serie '%s' selected via dropdown UI", serie)
            else:
                raise RuntimeError(f"Serie item not found in panel: {result}")
        except Exception as _e:
            log.warning(
                "Serie dropdown UI failed (%s) — falling back to jQuery trigger", _e
            )
            serie_input_id = _SERIE + "_input"
            opts = self.driver.execute_script(
                "var sel = document.getElementById(arguments[0]);"
                "if (!sel) return [];"
                "return Array.from(sel.options).map(function(o){"
                "  return {v: o.value, t: o.text.trim()};"
                "});",
                serie_input_id,
            )
            target_lower = serie.lower()
            matched_value = None
            for opt in (opts or []):
                if target_lower in opt.get("t", "").lower():
                    matched_value = opt["v"]
                    break
            if matched_value is not None:
                self.driver.execute_script(
                    "var el = document.getElementById(arguments[0]);"
                    "el.value = arguments[1];"
                    "window.jQuery(el).trigger('change');",
                    serie_input_id, matched_value,
                )
                wait_for_ajax(self.driver)
                log.info("Serie '%s' set via jQuery fallback (value=%s)", serie, matched_value)
            else:
                log.error("Serie '%s' not found in options: %s", serie, opts)

    # ── Pago header fields ───────────────────────────────────────────────────

    def fill_fecha_pago(self, fecha_str: str):
        """Set Fecha de Pago using jQuery datepicker's setDate API.

        Accepts: 'dd/mm/yyyy', 'yyyy-mm-dd', or 'dd-mm-yyyy'.
        Uses JS directly to avoid status-dialog overlay collision.
        """
        import time as _time
        target = _parse_fecha(fecha_str)
        log.info("fill_fecha_pago: %s → %s", fecha_str, target.strftime("%d/%m/%Y"))

        input_id = "formNuevaFactura:accordionDatosComprobante:fechaPago_input"

        # Wait for any lingering spinner/overlay to disappear before acting
        wait_for_ajax(self.driver)
        _time.sleep(0.5)

        # jQuery datepicker.setDate sets value + fires select events
        self.driver.execute_script(
            "var id = arguments[0];"
            "var d = new Date(arguments[1], arguments[2] - 1, arguments[3]);"
            "var escaped = '#' + id.replace(/:/g, '\\\\:');"
            "window.jQuery(escaped).datepicker('setDate', d);"
            "window.jQuery(document.getElementById(id)).trigger('change');",
            input_id, target.year, target.month, target.day,
        )
        wait_for_ajax(self.driver)

        # Verify the input value was set
        try:
            val = self.driver.find_element(By.ID, input_id).get_attribute("value")
            log.info("Fecha de Pago value after set: %s", val)
        except Exception:
            pass

    def fill_forma_pago_complemento(self, forma_pago: str):
        """Select Forma de Pago via jQuery trigger on hidden PrimeFaces select.

        Options use Java-hash values (CatFormaPagoSatDto@hash), so we match by
        display text (e.g. '01' matches '01 Efectivo') and set that hash value.
        """
        import time as _time
        log.info("fill_forma_pago_complemento: %s", forma_pago)
        wait_for_ajax(self.driver)
        _time.sleep(0.3)

        input_id = _FORMA_PAGO_PAGOP + "_input"
        opts = self.driver.execute_script(
            "var sel = document.getElementById(arguments[0]);"
            "return Array.from(sel.options).map(function(o){"
            "  return {v: o.value, t: o.text.trim()};"
            "});",
            input_id,
        )
        log.info("Forma de Pago options (first 5): %s", (opts or [])[:5])

        target_lower = forma_pago.lower()
        matched_value = None
        for opt in (opts or []):
            if opt.get("t", "").lower().startswith(target_lower):
                matched_value = opt["v"]
                break

        if matched_value is not None:
            self.driver.execute_script(
                "var el = document.getElementById(arguments[0]);"
                "el.value = arguments[1];"
                "window.jQuery(el).trigger('change');",
                input_id, matched_value,
            )
            wait_for_ajax(self.driver)
            log.info("Forma de Pago set via jQuery trigger (value=%s)", matched_value)
        else:
            log.warning(
                "Forma de Pago '%s' not found in options %s — falling back to UI",
                forma_pago, opts,
            )
            self.select_one_menu_contains(_FORMA_PAGO_PAGOP, forma_pago)
            wait_for_ajax(self.driver)

    def fill_moneda_pago_complemento(self, moneda: str):
        """Fill Moneda autocomplete in the CP pago panel.

        The field is pre-populated with MXN by the app.  If the desired moneda
        already matches the current input value, skip interaction entirely.
        """
        import time as _time
        log.info("fill_moneda_pago_complemento: %s", moneda)
        try:
            current = self.driver.find_element(
                By.ID, _MONEDA_PAGO_P_AC
            ).get_attribute("value") or ""
            if current.strip().upper() == moneda.strip().upper():
                log.info("Moneda de Pago already '%s' — skipping", current)
                return
        except Exception:
            pass
        wait_for_ajax(self.driver)
        _time.sleep(0.3)
        self.autocomplete(_MONEDA_PAGO_P_AC, moneda, moneda)
        wait_for_ajax(self.driver)

    # ── DR (Documento Relacionado) flow ─────────────────────────────────────

    def click_documento_relacionado_dr(self):
        """Click 'Documento Relacionado (DR)' button to open j_idt293 dialog."""
        log.info("Opening DR section dialog (j_idt293)")
        self.safe_click(_BTN_DR_SECTION)
        wait_for_element_visible(self.driver, By.ID, _DIALOG_DR_ID, timeout=20)
        wait_for_ajax(self.driver)

    def buscar_y_agregar_cfdi_en_dr(
        self,
        uuid_factura: str,
        emisor_rfc: str = "",
        sucursal: str = "",
        cc: str = "",
    ):
        """Inside j_idt293: open CFDI search modal, fill filters, search by UUID, add row 0.

        The search dialog requires Emisor, Sucursal and Centro de Consumo to be
        selected before a search yields any results.  Pass the same values used
        in fill_emisor so the correct CFDI list is queried.

        After this call j_idt293 is still open; call fill_importe_pago next.
        """
        import time as _time
        log.info("buscar_y_agregar_cfdi_en_dr: uuid=%s", uuid_factura)

        # "Buscar" inside j_idt293 → opens dialogDocRelacionado
        self.safe_click(_BTN_BUSCAR_EN_DR)
        wait_for_element_visible(
            self.driver, By.ID, _DIALOG_BUSQUEDA_ID, timeout=20
        )
        wait_for_ajax(self.driver)
        _time.sleep(0.3)

        # — Filter by Emisor (triggers AJAX to load Sucursal/CC options) —
        if emisor_rfc:
            log.info("DR search: setting Emisor=%s", emisor_rfc)
            _sel = _EMISOR_DR_SEARCH + "_input"
            if self._jquery_select_by_text(_sel, emisor_rfc):
                wait_for_ajax(self.driver)
                _time.sleep(0.3)

        # — Filter by Sucursal (triggers AJAX to load CC options) —
        if sucursal:
            log.info("DR search: setting Sucursal=%s", sucursal)
            _sel = _SUCURS_DR_SEARCH + "_input"
            if self._jquery_select_by_text(_sel, sucursal):
                wait_for_ajax(self.driver)
                _time.sleep(0.3)

        # — Filter by Centro de Consumo —
        if cc:
            log.info("DR search: setting CC=%s", cc)
            _sel = _CC_DR_SEARCH + "_input"
            if self._jquery_select_by_text(_sel, cc):
                wait_for_ajax(self.driver)
                _time.sleep(0.3)

        # Fill UUID and run search
        uuid_input = wait_for_element_clickable(
            self.driver, By.ID, _UUID_BUSQUEDA_INPUT, timeout=15
        )
        uuid_input.clear()
        uuid_input.send_keys(uuid_factura)
        self.safe_click(_BTN_BUSCAR_CFDI)
        wait_for_ajax(self.driver)

        # "Agregar" on result row 0 — modal auto-closes on click
        agregar_btn = wait_for_element_clickable(
            self.driver, By.CSS_SELECTOR, _BTN_AGREGAR_RESULT_0_CSS, timeout=20
        )
        self.scroll_to(agregar_btn)
        agregar_btn.click()
        wait_for_ajax(self.driver)
        log.info("CFDI row 0 added from search dialog")

    def fill_importe_pago(self, importe: str):
        """Fill the Importe de Pago field inside j_idt293."""
        log.info("fill_importe_pago: %s", importe)
        el = wait_for_element_clickable(
            self.driver, By.ID, _IMPORTE_PAGO_INPUT, timeout=15
        )
        el.clear()
        el.send_keys(importe)
        wait_for_ajax(self.driver)

    def click_agregar_en_dialog_dr(self):
        """Click 'Agregar' (j_idt350) inside j_idt293 to commit the DR row."""
        log.info("Clicking Agregar in j_idt293 (j_idt350)")
        self.safe_click(_BTN_AGREGAR_EN_DR)
        wait_for_ajax(self.driver)

    def close_dialog_dr(self):
        """Close the j_idt293 dialog via its X button."""
        log.info("Closing j_idt293 dialog")
        self.safe_click_css(_DIALOG_DR_CLOSE_CSS)
        wait_for_ajax(self.driver)

    def click_agregar_pago(self):
        """Click 'Agregar pago' (j_idt418) in the main form."""
        log.info("Clicking Agregar pago (j_idt418)")
        self.safe_click(_BTN_AGREGAR_PAGO)
        wait_for_ajax(self.driver)

    # ── High-level orchestrator ──────────────────────────────────────────────

    def flujo_dr_completo(
        self,
        uuid_factura: str,
        importe_pago: str,
        emisor_rfc: str = "",
        sucursal: str = "",
        cc: str = "",
    ):
        """Orchestrate the full DR sub-flow (steps 7-12):

          click_documento_relacionado_dr()
          buscar_y_agregar_cfdi_en_dr(uuid_factura, emisor_rfc, sucursal, cc)
          fill_importe_pago(importe_pago)
          click_agregar_en_dialog_dr()
          close_dialog_dr()
          click_agregar_pago()
        """
        self.click_documento_relacionado_dr()
        self.buscar_y_agregar_cfdi_en_dr(
            uuid_factura,
            emisor_rfc=emisor_rfc,
            sucursal=sucursal,
            cc=cc,
        )
        self.fill_importe_pago(importe_pago)
        self.click_agregar_en_dialog_dr()
        self.close_dialog_dr()
        self.click_agregar_pago()

    def timbrar_complemento(self, timeout: int = 60) -> str:
        """Click Facturar and return UUID."""
        return self.click_facturar(timeout=timeout)

    # ── Private helpers ─────────────────────────────────────────────────────

    def _jquery_select_by_text(self, input_id: str, text: str) -> bool:
        """Set a PrimeFaces hidden <select> to the first option whose display
        text contains *text* (case-insensitive) and fire the jQuery change event.

        Returns True if an option was found and set, False otherwise.
        """
        opts = self.driver.execute_script(
            "var sel = document.getElementById(arguments[0]);"
            "if (!sel) return null;"
            "return Array.from(sel.options).map(function(o){"
            "  return {v: o.value, t: o.text.trim()};"
            "});",
            input_id,
        )
        if opts is None:
            log.warning("_jquery_select_by_text: element '%s' not found", input_id)
            return False
        target_lower = text.lower()
        matched_value = None
        for opt in opts:
            if target_lower in opt.get("t", "").lower():
                matched_value = opt["v"]
                break
        if matched_value is not None:
            self.driver.execute_script(
                "var el = document.getElementById(arguments[0]);"
                "el.value = arguments[1];"
                "window.jQuery(el).trigger('change');",
                input_id, matched_value,
            )
            log.info(
                "jQuery select: '%s' matched '%s' → value=%s",
                input_id, text, matched_value,
            )
            return True
        log.warning(
            "_jquery_select_by_text: no option matching '%s' in %s", text, (opts or [])[:5]
        )
        return False


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_fecha(fecha_str: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(fecha_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Unrecognized date format: {fecha_str!r}  "
        f"(accepted: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy)"
    )


def _nav_to_month(driver, target: datetime, max_clicks: int = 36):
    """Navigate the jQuery-UI datepicker to the target month/year.

    Reads the title text (e.g. "marzo 2026"), splits on the last token for the
    year and uses the rest for the month name (handles multi-word month names).
    Clicks NEXT/PREV arrows until current month == target month.
    """
    for _ in range(max_clicks):
        try:
            title_el = driver.find_element(By.CSS_SELECTOR, _DP_TITLE)
            title_text = title_el.text.strip().lower()
        except Exception:
            break  # panel gone or not yet rendered

        # title format: "marzo 2026" or "Marzo de 2026" — year is always last word
        parts = title_text.split()
        if len(parts) < 2:
            break
        try:
            cur_year = int(parts[-1])
        except ValueError:
            break

        cur_month = 0
        for word in parts[:-1]:
            if word in _ES_MONTHS:
                cur_month = _ES_MONTHS[word]
                break

        if cur_month == 0:
            log.warning("Could not parse month from datepicker title: %r", title_text)
            break

        if cur_year == target.year and cur_month == target.month:
            return

        if (cur_year, cur_month) < (target.year, target.month):
            driver.find_element(By.CSS_SELECTOR, _DP_NEXT).click()
        else:
            driver.find_element(By.CSS_SELECTOR, _DP_PREV).click()

        wait_for_ajax(driver)

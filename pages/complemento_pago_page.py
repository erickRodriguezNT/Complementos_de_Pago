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

import time as _time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
# Selector estable para el botón Agregar de la fila 0 de resultados.
# No usa el sufijo j_idt* (dinámico), sino el ID de fila fijo + tipo button.
_BTN_AGREGAR_RESULT_0_CSS = (
    r"#formNuevaFactura\:dataTableBusquedaDocRelacionado\:0 button"
)# Campos de fecha del filtro DR (readonly + onblur=null → solo se setean por JS)
# Nota: "Del" tiene un typo en el ID de la app (Busuqeda, no Busqueda)
_CAL_DR_DEL_INPUT  = "formNuevaFactura:calendarBusuqedaDocRelDel_input"   # Emisión Del
_CAL_DR_AL_INPUT   = "formNuevaFactura:calendarBusquedaDocRelAl_input"    # Emisión Al
_CAL_DR_DEL_BTN    = r"#formNuevaFactura\:calendarBusuqedaDocRelDel button.ui-datepicker-trigger"
_CAL_DR_AL_BTN     = r"#formNuevaFactura\:calendarBusquedaDocRelAl button.ui-datepicker-trigger"
# ── "Agregar pago" button in main form ──────────────────────────────────────
_BTN_AGREGAR_PAGO = "formNuevaFactura:accordionDatosComprobante:j_idt418"
# ── Tipo de Cambio Pago / Equivalencia DR ─────────────────────────────────────
_INPUT_TIPO_CAMBIO_PAGO = (
    "formNuevaFactura:accordionDatosComprobante:inputTipoCambioP_input"
)
_INPUT_EQUIVALENCIA_DR = (
    "formNuevaFactura:accordionDatosComprobante:tipoCambioRelacionadoComplemento_input"
)
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
        _time.sleep(0.2)

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
        # li item via JavaScript
        wait_for_ajax(self.driver)
        _time.sleep(0.1)
        log.info("Serie: opening dropdown to select '%s'", serie)
        try:
            trigger = wait_for_element_clickable(self.driver, By.ID, _SERIE, timeout=10)
            self.scroll_to(trigger)
            try:
                trigger.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", trigger)
            _time.sleep(0.2)

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

        # ─ Verificación DOM final de Serie ─
        # Independientemente de cuál rama se ejecutó arriba, confirmar que el
        # label visible refleja la serie correcta.  Si no, un último reintento
        # con force_select para garantizar el campo antes de continuar.
        try:
            serie_label = (
                self.driver.find_element(By.ID, _SERIE + "_label")
                .get_attribute("textContent") or ""
            ).strip()
            if serie.lower() not in serie_label.lower():
                log.warning(
                    "Serie label muestra '%s' (esperado '%s') — forzando con force_select",
                    serie_label, serie,
                )
                self.force_select_contains(_SERIE, serie)
            else:
                log.info("Serie '%s' confirmada en DOM: '%s'", serie, serie_label)
        except Exception as _ve:
            log.warning("No se pudo verificar label de Serie: %s", _ve)

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
        _time.sleep(0.2)

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
        _time.sleep(0.1)

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
            # Confirmar que el label visible se actualizó
            try:
                label_id = _FORMA_PAGO_PAGOP + "_label"
                label_txt = self.driver.find_element(By.ID, label_id).text.strip()
                if forma_pago.lower()[:2] in label_txt.lower():
                    log.info("[fill_forma_pago_complemento] Campo confirmado en DOM: '%s'", label_txt)
                else:
                    log.warning(
                        "[fill_forma_pago_complemento] Label '%s' no coincide con '%s' — forzando con force_jquery",
                        label_txt, forma_pago,
                    )
                    self.force_jquery(input_id, forma_pago)
            except Exception:
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
        _time.sleep(0.1)
        # force_ac incluye retry + validaão DOM; lanza FieldFillError si falla
        self.force_ac(_MONEDA_PAGO_P_AC, moneda, moneda)

    def fill_tipo_cambio_pago(self, tipo_cambio: float):
        """Fill 'Tipo de Cambio Pago *' field (enabled only when moneda ≠ MXN).

        Call after fill_moneda_pago_complemento with a non-MXN moneda.
        Uses a Selenium fallback to JS in case the field is still disabled.
        """
        if tipo_cambio <= 0:
            return
        import time as _time
        log.info("fill_tipo_cambio_pago: %.4f", tipo_cambio)
        wait_for_ajax(self.driver)
        _time.sleep(0.3)
        valor_str = str(tipo_cambio)
        try:
            el = wait_for_element_clickable(
                self.driver, By.ID, _INPUT_TIPO_CAMBIO_PAGO, timeout=10
            )
            el.clear()
            el.send_keys(valor_str)
        except Exception:
            log.warning("fill_tipo_cambio_pago: Selenium interaction failed — using JS fallback")
            self.driver.execute_script(
                "var inp = document.getElementById(arguments[0]);"
                "var hid = document.getElementById("
                "    arguments[0].replace('_input','_hinput'));"
                "if (inp) {"
                "    inp.removeAttribute('disabled');"
                "    inp.value = arguments[1];"
                "    window.jQuery(inp).trigger('change');"
                "}"
                "if (hid) {"
                "    hid.removeAttribute('disabled');"
                "    hid.value = arguments[1];"
                "}",
                _INPUT_TIPO_CAMBIO_PAGO, valor_str,
            )
        wait_for_ajax(self.driver)

    def fill_equivalencia_dr(self, equivalencia: float):
        """Fill 'Equivalencia DR' inside j_idt293 dialog.

        Call after buscar_y_agregar_cfdi_en_dr and before fill_importe_pago.
        Represents the ratio of document currency to payment currency
        (e.g. 1/tipo_cambio_pago when document is MXN and payment is USD).
        """
        if equivalencia <= 0:
            return
        import time as _time
        log.info("fill_equivalencia_dr: %.6f", equivalencia)
        wait_for_ajax(self.driver)
        _time.sleep(0.2)
        el = wait_for_element_clickable(
            self.driver, By.ID, _INPUT_EQUIVALENCIA_DR, timeout=15
        )
        el.clear()
        el.send_keys(str(equivalencia))
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
        max_filter_attempts: int = 3,
    ):
        """Inside j_idt293: open CFDI search modal, fill filters, search by UUID, add row 0.

        Emisor triggers an AJAX cascade that populates Sucursal, which in turn
        populates CC.  After each step we WAIT until the dependent select has
        more than 1 option before proceeding, then retry up to max_filter_attempts
        times if options failed to load or the value didn't stick.

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

        # ───────────────────────────────────────────────────────────────────────
        # Seleccionar filtros con reintentos + espera de opciones dependientes
        # ───────────────────────────────────────────────────────────────────────
        filters_ok = False
        for _fa in range(1, max_filter_attempts + 1):

            # — Emisor —
            if emisor_rfc:
                log.info("DR search: setting Emisor=%s (attempt %d)", emisor_rfc, _fa)
                _sel = _EMISOR_DR_SEARCH + "_input"
                if self._jquery_select_by_text(_sel, emisor_rfc):
                    wait_for_ajax(self.driver)
                    # Esperar a que AJAX cargue las opciones de Sucursal
                    if sucursal:
                        loaded = self._wait_for_select_options(
                            _SUCURS_DR_SEARCH + "_input", min_options=2, timeout=12
                        )
                        if not loaded:
                            log.warning(
                                "DR: Sucursal options not loaded after 12 s (attempt %d/%d)",
                                _fa, max_filter_attempts,
                            )
                            _time.sleep(0.5)
                            continue  # reintentar todo el bloque
                else:
                    log.warning("DR: Emisor not set (attempt %d/%d)", _fa, max_filter_attempts)
                    _time.sleep(0.5)
                    continue

            # — Sucursal —
            if sucursal:
                log.info("DR search: setting Sucursal=%s (attempt %d)", sucursal, _fa)
                _sel = _SUCURS_DR_SEARCH + "_input"
                if self._jquery_select_by_text(_sel, sucursal):
                    wait_for_ajax(self.driver)
                    # Esperar a que AJAX cargue las opciones de CC
                    if cc:
                        loaded = self._wait_for_select_options(
                            _CC_DR_SEARCH + "_input", min_options=2, timeout=12
                        )
                        if not loaded:
                            log.warning(
                                "DR: CC options not loaded after 12 s (attempt %d/%d)",
                                _fa, max_filter_attempts,
                            )
                            _time.sleep(0.5)
                            continue
                else:
                    log.warning(
                        "DR: Sucursal '%s' not set (options may not be loaded) — attempt %d/%d",
                        sucursal, _fa, max_filter_attempts,
                    )
                    # Volver a disparar el cambio de Emisor para refrescar opciones
                    if emisor_rfc:
                        self._jquery_select_by_text(
                            _EMISOR_DR_SEARCH + "_input", emisor_rfc
                        )
                        wait_for_ajax(self.driver)
                        self._wait_for_select_options(
                            _SUCURS_DR_SEARCH + "_input", min_options=2, timeout=12
                        )
                    _time.sleep(0.5)
                    continue

            # — Centro de Consumo —
            if cc:
                log.info("DR search: setting CC=%s (attempt %d)", cc, _fa)
                _sel = _CC_DR_SEARCH + "_input"
                if not self._jquery_select_by_text(_sel, cc):
                    log.warning(
                        "DR: CC '%s' not set — attempt %d/%d",
                        cc, _fa, max_filter_attempts,
                    )
                    _time.sleep(0.5)
                    continue
                wait_for_ajax(self.driver)

            filters_ok = True
            break  # todos los filtros aplicados ✔

        if not filters_ok:
            log.warning(
                "DR: filtros no aplicados completamente tras %d intentos; "
                "procediendo de todos modos",
                max_filter_attempts,
            )

        # ───────────────────────────────────────────────────────────────────────
        # Buscar por UUID
        # ───────────────────────────────────────────────────────────────────────
        uuid_input = wait_for_element_clickable(
            self.driver, By.ID, _UUID_BUSQUEDA_INPUT, timeout=15
        )
        uuid_input.clear()
        uuid_input.send_keys(uuid_factura)

        # Cerrar datepicker si quedó abierto (cubre el botón Buscar)
        self._dismiss_datepicker_dr()

        # Localizar el botón Buscar por texto dentro del diálogo.
        # _BTN_BUSCAR_CFDI usa un ID dinámico (j_idt*) que cambia entre renders;
        # buscar por texto es estable.
        _BUSCAR_XPATH = (
            "//div[@id='formNuevaFactura:dialogDocRelacionado']"
            "//button[normalize-space(.)='Buscar']"
        )
        log.info("[INFO] DR: localizando botón Buscar por texto dentro del diálogo")
        buscar_btn = wait_for_element_clickable(
            self.driver, By.XPATH, _BUSCAR_XPATH, timeout=10
        )
        self.scroll_to(buscar_btn)
        log.info("[INFO] DR: haciendo clic en botón Buscar (id=%s)", buscar_btn.get_attribute("id"))
        # JS click evita cualquier overlay (calendar input, label, etc.) que
        # intercepte el click normal de Selenium.
        self.driver.execute_script("arguments[0].click();", buscar_btn)

        # wait_for_ajax sólo detecta div.ui-blockui-document, que el AJAX del Buscar
        # no siempre dispara.  Esperar EXPLÍCITAMENTE a que la tabla muestre
        # resultados O el mensaje vacío (máx 30 s).
        _FILA0_XPATH = (
            "//tr[contains(@id,'formNuevaFactura:dataTableBusquedaDocRelacionado:0')]"
        )
        _EMPTY_XPATH = (
            "//*[contains(@id,'dataTableBusquedaDocRelacionado')]"
            "//*[contains(@class,'ui-datatable-empty-message')]"
        )
        log.info("[INFO] DR: esperando resultados del Buscar (máx 30s)...")
        try:
            WebDriverWait(self.driver, 30).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, _FILA0_XPATH)),
                    EC.presence_of_element_located((By.XPATH, _EMPTY_XPATH)),
                )
            )
        except Exception:
            pass  # continuar — el diagnóstico abajo reportará el estado real

        # Diagnóstico: contar filas de resultado
        filas = self.driver.execute_script(
            "var t = document.querySelector('[id$=\"dataTableBusquedaDocRelacionado_data\"]');"
            "if (!t) return -1;"
            "return t.querySelectorAll('tr:not([class*=\"empty\"])').length;"
        )
        log.info("[INFO] DR: tabla de resultados tiene %s fila(s)", filas)

        # Detectar mensajes de validación (Sucursal requerida / CC requerido)
        val_msgs = self.driver.execute_script(
            "return Array.from(document.querySelectorAll("
            "  '.ui-messages-error-summary, .ui-message-error-summary, "
            "   span.ui-messages-error-summary'"
            ")).map(function(e){ return e.textContent.trim(); });"
        ) or []
        required_errors = [m for m in val_msgs if "requerida" in m.lower() or "requerido" in m.lower()]
        if required_errors:
            raise RuntimeError(
                f"DR Buscar: validación fallida — {required_errors}. "
                "Sucursal/CC no se aplicaron correctamente."
            )

        if filas == 0:
            raise RuntimeError(
                f"DR: la búsqueda no devolvió resultados para UUID '{uuid_factura}'. "
                "Verificar que la factura esté timbrada y que los filtros coincidan."
            )

        # Botón Agregar en fila 0.
        # El sufijo j_idt* cambia entre renders; el prefijo de fila es estable:
        #   formNuevaFactura:dataTableBusquedaDocRelacionado:0:<j_idt>
        # Se usa wait_for_element_visible (no clickable) porque PrimeFaces a veces
        # no marca el botón como "enabled" en el check de Selenium.
        # JS click evita cualquier overlay residual.
        _AGREGAR_FILA0_XPATH = (
            "//button[contains(@id,':dataTableBusquedaDocRelacionado:0:')]"
        )
        log.info("[INFO] DR: localizando botón Agregar en fila 0 (por ID de fila)")
        agregar_btn = wait_for_element_visible(
            self.driver, By.XPATH, _AGREGAR_FILA0_XPATH, timeout=10
        )
        self.scroll_to(agregar_btn)
        log.info("[INFO] DR: clic en Agregar fila 0 (id=%s)", agregar_btn.get_attribute("id"))
        self.driver.execute_script("arguments[0].click();", agregar_btn)
        wait_for_ajax(self.driver)
        log.info("[INFO] DR: CFDI fila 0 agregado desde diálogo de búsqueda")

    # ── Helpers de fecha DR ─────────────────────────────────────────────────

    def _dismiss_datepicker_dr(self):
        """Cierra el overlay del jQuery-UI datepicker si está visible.

        Los inputs de fecha DR son readonly + onblur="this.value = null".
        Si el picker quedó abierto (por interacción anterior u onload) cubre
        el botón Buscar y provoca "element click intercepted".

        Estrategia:
          1. Ocultar el overlay vía JS (más rápido y confiable que ESC).
          2. Verificar que ya no es visible.
        """
        try:
            visible = self.driver.execute_script(
                "var dp = document.getElementById('ui-datepicker-div');"
                "return dp ? (dp.style.display !== 'none' && dp.offsetHeight > 0) : false;"
            )
            if visible:
                log.info("[INFO] DR: cerrando datepicker abierto antes de Buscar")
                self.driver.execute_script(
                    "var dp = document.getElementById('ui-datepicker-div');"
                    "if (dp) { dp.style.display = 'none'; }"
                )
                _time.sleep(0.1)
        except Exception as _e:
            log.debug("_dismiss_datepicker_dr: %s", _e)

    def _set_fecha_dr(self, input_id: str, fecha_str: str, max_attempts: int = 2) -> bool:
        """Setea una fecha en los inputs readonly del filtro DR sin hacer click en el label.

        Los inputs de fecha DR son:
          - readonly="readonly"
          - onblur="this.value = null"   ← limpiará el valor si pierde el foco via blur normal

        Estrategia:
          1. Desactivar temporalmente el onblur para que no borre el valor.
          2. Asignar value directamente por JS.
          3. Disparar evento 'change' para notificar a jQuery-UI.
          4. Verificar que el valor quedó.
          5. Restaurar onblur al salir.

        El formato esperado es dd/mm/yyyy (como PrimeFaces lo muestra en el input).

        Args:
            input_id:   ID del input, ej. "formNuevaFactura:calendarBusquedaDocRelAl_input"
            fecha_str:  Fecha en cualquier formato soportado: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy
            max_attempts: Reintentos si el valor no persiste.

        Returns:
            True si el valor quedó confirmado, False si no persistió.
        """
        # Normalizar a dd/mm/yyyy (formato que el input muestra)
        dt = None
        for fmt in _DATE_FORMATS:
            try:
                dt = datetime.strptime(fecha_str.strip(), fmt)
                break
            except ValueError:
                continue
        if dt is None:
            log.warning("[_set_fecha_dr] Formato de fecha no reconocido: '%s'", fecha_str)
            return False

        valor_ui = dt.strftime("%d/%m/%Y")
        log.info("[INFO] DR fecha: usando input real, no label — id=%s valor=%s", input_id, valor_ui)

        for attempt in range(1, max_attempts + 1):
            ok = self.driver.execute_script(
                """
                var el = document.getElementById(arguments[0]);
                if (!el) return false;
                // Desactivar onblur temporalmente
                var orig = el.onblur;
                el.onblur = null;
                // Quitar readonly para poder setear value (no siempre necesario pero es seguro)
                el.removeAttribute('readonly');
                // Setear valor
                el.value = arguments[1];
                // Disparar eventos para notificar a jQuery-UI datepicker
                try { el.dispatchEvent(new Event('input',  {bubbles:true})); } catch(e) {}
                try { el.dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
                // Restaurar readonly y onblur
                el.setAttribute('readonly', 'readonly');
                el.onblur = orig;
                // Verificar que quedó
                return el.value === arguments[1];
                """,
                input_id, valor_ui,
            )
            if ok:
                log.info("[INFO] DR fecha seteada correctamente: %s = %s", input_id, valor_ui)
                return True
            log.warning(
                "[WARNING] DR fecha no persistió (intento %d/%d) — reintentando",
                attempt, max_attempts,
            )
            _time.sleep(0.3)

        log.error("[ERROR] DR fecha no pudo establecerse: %s = %s", input_id, valor_ui)
        return False

    def fill_importe_pago(self, importe: str):
        """Fill the Importe de Pago field inside j_idt293 con validación DOM."""
        log.info("[fill_importe_pago] Forzando campo: Importe Pago → %s", importe)
        self.force_input(_IMPORTE_PAGO_INPUT, str(importe))
        wait_for_ajax(self.driver)
        try:
            val = self.driver.find_element(By.ID, _IMPORTE_PAGO_INPUT).get_attribute("value")
            log.info("[fill_importe_pago] Campo confirmado en DOM: Importe Pago = %s", val)
        except Exception:
            pass

    def click_agregar_en_dialog_dr(self):
        """Click 'Agregar' (j_idt350) inside j_idt293 y verifica que no haya error funcional."""
        log.info("Clicking Agregar in j_idt293 (j_idt350)")
        self.safe_click(_BTN_AGREGAR_EN_DR)
        wait_for_ajax(self.driver)
        # Si el Agregar produjo error (ej. importe inválido, UUID no encontrado)
        # el growl interceptará el cierre del modal — detectarlo antes de continuar.
        self._check_growl_error(context="click_agregar_en_dialog_dr")

    def close_dialog_dr(self):
        """Verifica que no haya error funcional y cierra el diálogo j_idt293.

        IMPORTANTE: si existe growl error el click en X sería interceptado por
        el growl (element click intercepted). Se debe detectar y relanzar antes.
        """
        self._check_growl_error(context="close_dialog_dr")
        log.info("Closing j_idt293 dialog")
        self.safe_click_css(_DIALOG_DR_CLOSE_CSS)
        wait_for_ajax(self.driver)

    def click_agregar_pago(self):
        """Click 'Agregar pago' (j_idt418) in the main form.

        After clicking, waits until the button disappears or becomes stale
        (indicates the pago row was registered by the server-side AJAX) before
        returning.  Without this guard the timbrado fires before the form
        state is complete and the server returns 'La información de Pago es
        requerida'.
        """
        log.info("Clicking Agregar pago (j_idt418)")
        self.safe_click(_BTN_AGREGAR_PAGO)
        wait_for_ajax(self.driver)
        # Extra confirmation: wait up to 10 s for the button to become
        # temporarily invisible/stale (server AJAX re-renders the section)
        # or for a new pago row to appear.  Both signal the pago was saved.
        try:
            WebDriverWait(self.driver, 10).until(
                EC.any_of(
                    EC.staleness_of(
                        self.driver.find_element(By.ID, _BTN_AGREGAR_PAGO)
                    ),
                    EC.invisibility_of_element_located(
                        (By.ID, _BTN_AGREGAR_PAGO)
                    ),
                )
            )
        except Exception:
            _time.sleep(2)  # safety pause if the button didn't change state
        wait_for_ajax(self.driver)

    # ── High-level orchestrator ──────────────────────────────────────────────

    def flujo_dr_completo(
        self,
        uuid_factura: str,
        importe_pago: str,
        emisor_rfc: str = "",
        sucursal: str = "",
        cc: str = "",
        equivalencia_dr: float = 0.0,
    ):
        """Orchestrate the full DR sub-flow (steps 7-12):

          click_documento_relacionado_dr()
          buscar_y_agregar_cfdi_en_dr(uuid_factura, emisor_rfc, sucursal, cc)
          fill_equivalencia_dr(equivalencia_dr)   # only if equivalencia_dr > 0
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
        if equivalencia_dr > 0:
            self.fill_equivalencia_dr(equivalencia_dr)
        self.fill_importe_pago(importe_pago)
        self.click_agregar_en_dialog_dr()
        self.close_dialog_dr()
        self.click_agregar_pago()

    def read_datos_dr_row(self) -> dict:
        """Lee Saldo Anterior, Pago y Saldo Insoluto de la última fila de tableDocRelacionado.

        Debe llamarse después de flujo_dr_completo() (que ya ejecutó click_agregar_pago).
        Los valores están en la moneda de la factura relacionada (MXN si la factura es MXN).

        Returns:
            dict con claves 'saldo_anterior', 'pago', 'saldo_insoluto' (float).
            Si la tabla está vacía o no se puede leer, retorna ceros.
        """
        wait_for_ajax(self.driver)
        _time.sleep(0.3)
        raw = self.driver.execute_script(
            """
            var tbody = document.getElementById(
                'formNuevaFactura:accordionDatosComprobante:tableDocRelacionado_data'
            );
            if (!tbody) return null;
            var rows = tbody.querySelectorAll('tr');
            var result = {saldo_anterior: '', pago: '', saldo_insoluto: ''};
            for (var i = rows.length - 1; i >= 0; i--) {
                var tds = rows[i].querySelectorAll('td');
                if (tds.length < 4) continue;
                for (var j = 0; j < tds.length; j++) {
                    var span = tds[j].querySelector('.ui-column-title');
                    if (!span) continue;
                    var key = span.textContent.trim();
                    var val = tds[j].textContent.replace(span.textContent, '').trim();
                    if (key === 'Saldo Anterior') result.saldo_anterior = val;
                    if (key === 'Pago') result.pago = val;
                    if (key === 'Saldo Insoluto') result.saldo_insoluto = val;
                }
                if (result.saldo_insoluto) break;
            }
            return result;
            """
        )
        if not raw:
            log.warning("read_datos_dr_row: tableDocRelacionado_data no encontrada o vacía")
            return {"saldo_anterior": 0.0, "pago": 0.0, "saldo_insoluto": 0.0}

        def _parse(val: str) -> float:
            if not val:
                return 0.0
            cleaned = str(val).replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return 0.0

        result = {
            "saldo_anterior": _parse(raw.get("saldo_anterior", "")),
            "pago": _parse(raw.get("pago", "")),
            "saldo_insoluto": _parse(raw.get("saldo_insoluto", "")),
        }
        log.info(
            "read_datos_dr_row: saldo_anterior=%.2f | pago=%.2f | saldo_insoluto=%.2f",
            result["saldo_anterior"], result["pago"], result["saldo_insoluto"],
        )
        return result

    def timbrar_complemento(self, timeout: int = 60) -> str:
        """Click Facturar and return UUID."""
        return self.click_facturar(timeout=timeout)

    # ── Private helpers ─────────────────────────────────────────────────────

    def _check_growl_error(self, context: str = "") -> None:
        """Lee el growl/toast de error activo y lanza RuntimeError si existe.

        Llama antes de operaciones críticas como cerrar el diálogo DR o
        después de clicks que podrían producir errores funcionales.
        """
        _time.sleep(0.4)  # dar tiempo a PrimeFaces para renderizar el growl
        msg = self.driver.execute_script(
            "var sels = ["
            "  '.ui-growl-message-error .ui-growl-message-summary',"
            "  '.ui-growl-message-error .ui-growl-message-detail',"
            "  '.ui-growl-item-container.ui-state-error .ui-growl-message-summary',"
            "  '.ui-growl-item-container.ui-state-error .ui-growl-message-detail',"
            "  '.ui-messages-error-summary',"
            "  '.ui-message-error-summary'"
            "];"
            "for (var s = 0; s < sels.length; s++) {"
            "  var els = document.querySelectorAll(sels[s]);"
            "  for (var e = 0; e < els.length; e++) {"
            "    var t = (els[e].textContent || '').trim();"
            "    if (t) return t;"
            "  }"
            "}"
            "return null;"
        )
        if msg:
            ctx = f" [{context}]" if context else ""
            log.error("[DR] Growl de error detectado%s: %s", ctx, msg)
            raise RuntimeError(f"ERROR_GROWL_DR{ctx}: {msg}")

    def _wait_for_select_options(
        self, input_id: str, min_options: int = 2, timeout: int = 12
    ) -> bool:
        """Poll until a <select> has at least *min_options* options.

        Needed because PrimeFaces cascades Sucursal/CC options via AJAX after
        Emisor/Sucursal selection.  Returns True when ready, False on timeout.
        """
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            count = self.driver.execute_script(
                "var s = document.getElementById(arguments[0]);"
                "return s ? s.options.length : 0;",
                input_id,
            )
            if count >= min_options:
                return True
            _time.sleep(0.3)
        return False

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
        target_lower = text.lower().strip()
        matched_value = None
        # Priority 1: exact match
        for opt in opts:
            if opt.get("t", "").lower().strip() == target_lower:
                matched_value = opt["v"]
                break
        # Priority 2: starts-with match
        if matched_value is None:
            for opt in opts:
                if opt.get("t", "").lower().strip().startswith(target_lower):
                    matched_value = opt["v"]
                    break
        # Priority 3: substring match (last resort)
        if matched_value is None:
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

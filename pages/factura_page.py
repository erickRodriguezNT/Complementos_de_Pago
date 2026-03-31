"""Factura Manual 4.0 Page Object.

Covers full CFDI 4.0 invoice creation flow:
  Emisor → Receptor → Comprobante → Conceptos → Timbrar → Download
"""
import os
import re
import time
from typing import List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

from pages.base_page import BasePage
from utils.waits import (
    wait_for_ajax, wait_for_element_clickable,
    wait_for_element_visible, wait_for_element_present,
    wait_for_toast, is_element_present,
)
from utils.excel_manager import ConceptoRow, ImpuestoRow
from utils.logger import get_logger

log = get_logger("factura_page")

# ═══════════════════════════════════════════════════════════════════════════════
# LOCATORS
# Elements confirmed from HTML snapshot; TODOs require live inspection.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Emisor ───────────────────────────────────────────────────────────────────
_EMISOR_SELECT      = "formNuevaFactura:accordionDatosEmisor:selectOneEmisores"
_EMISOR_FILTER      = "formNuevaFactura:accordionDatosEmisor:selectOneEmisores_filter"

_SUCURSAL_SELECT    = "formNuevaFactura:accordionDatosEmisor:selectOneSucursales"
_CC_SELECT          = "formNuevaFactura:accordionDatosEmisor:selectOneCentroConsumo"

# ── Receptor ─────────────────────────────────────────────────────────────────
_RFC_RECEPTOR       = "formNuevaFactura:accordionDatosReceptor:inputRfcReceptor"
_NOMBRE_RECEPTOR    = "formNuevaFactura:accordionDatosReceptor:inputNombreReceptor"
_USO_CFDI           = "formNuevaFactura:accordionDatosReceptor:selectOneUsoCfdi"
_REGIMEN_RECEPTOR   = "formNuevaFactura:accordionDatosReceptor:selectOneRegimenReceptor"
_DOMICILIO_RECEPTOR = "formNuevaFactura:accordionDatosReceptor:inputDomicilioReceptor"
_EMAIL_RECEPTOR     = "formNuevaFactura:accordionDatosReceptor:selectOneEmailReceptor"
_AUTOCOMPLETE_RFC   = "formNuevaFactura:accordionDatosReceptor:autoCompleteRfcReceptor_input"

# ── Comprobante ───────────────────────────────────────────────────────────────
_TIPO_COMPROBANTE       = "formNuevaFactura:accordionDatosComprobante:selectOneTipoComprobante"
_TIPO_COMPROBANTE_LABEL = "formNuevaFactura:accordionDatosComprobante:selectOneTipoComprobante_label"
_SERIE              = "formNuevaFactura:accordionDatosComprobante:selectOneSerie"
_FORMA_PAGO         = "formNuevaFactura:accordionDatosComprobante:selectOneFormaPago"
_METODO_PAGO        = "formNuevaFactura:accordionDatosComprobante:selectOneMetodoPago"
_MONEDA_AC          = "formNuevaFactura:accordionDatosComprobante:autoCompleteMoneda_input"
_INPUT_TIPO_CAMBIO   = "formNuevaFactura:accordionDatosComprobante:inputTipoCambio_input"

# ── Conceptos ────────────────────────────────────────────────────────────────
_INPUT_CANTIDAD     = "formNuevaFactura:accordionConceptos:inputCantidad_input"
_AC_CLAVE_UNIDAD    = "formNuevaFactura:accordionConceptos:autoCompleteClaveUnidad_input"
_INPUT_UNIDAD       = "formNuevaFactura:accordionConceptos:inputUnidad"
_AC_DESCRIPCION     = "formNuevaFactura:accordionConceptos:autoCompleteConceptoDescripcion_input"
_AC_CLAVE_PROD      = "formNuevaFactura:accordionConceptos:autoCompleteClaveProducto_input"
_INPUT_VALOR_UNIT   = "formNuevaFactura:accordionConceptos:inputValorUnitario_input"
_OBJETO_IMP         = "formNuevaFactura:accordionConceptos:selectOneObjetoImp"
_BTN_EXPANDIR_IMPUESTOS_CSS = r"#formNuevaFactura\:accordionConceptos\:filedSetImpuestos > legend > span"
_FIELDSET_IMPUESTOS_CSS = r"#formNuevaFactura\:accordionConceptos\:filedSetImpuestos"

# Impuesto sub-form
_SEL_IMPUESTO       = "formNuevaFactura:accordionConceptos:selectOneImpuestos"
_SEL_LOCAL_FED      = "formNuevaFactura:accordionConceptos:selectOneImpuestosLocalFederal"
_SEL_TRASLADO_RET   = "formNuevaFactura:accordionConceptos:selectOneImpuestosTrasladoRetencion"
_SEL_TIPO_FACTOR    = "formNuevaFactura:accordionConceptos:selectOneImpuestosTipoFactor"
_INPUT_TASA         = "formNuevaFactura:accordionConceptos:inputNumberTasaCuota_input"
_BTN_AGREGAR_IMP    = "formNuevaFactura:accordionConceptos:j_idt1648"
_BTN_AGREGAR_CONC   = "formNuevaFactura:accordionConceptos:buttonAgregarConcepto"
_PANEL_TOTALES      = "formNuevaFactura:accordionConceptos:panelGridTotales"

# ── Action buttons (dynamic — appear after first concepto added) ──────────────
_PANEL_BOTONES      = "formNuevaFactura:panelGridBotonesFacturacion"
_BTN_FACTURAR       = "formNuevaFactura:buttonTimbrar"   # TODO — verify exact id
_BTN_DESCARGA       = "formNuevaFactura:buttonDescargaCFDI"  # TODO — verify exact id
# CSS fallback
_BTN_FACTURAR_CSS   = "#formNuevaFactura\\:panelGridBotonesFacturacion button[id*='Timbrar'], #formNuevaFactura\\:panelGridBotonesFacturacion button[id*='acturar']"
_BTN_DESCARGA_CSS   = "button[id*='escarga'], a[id*='escarga']"


# Menú lateral — ítem confirmado del DOM snapshot
_MENU_FACTURA40_CSS = "#menuform\\:facManualmenu40 a"

# Fragmento de URL que identifica que ya estamos en la página de factura
_FACTURA_URL_FRAGMENT = "factura_manual_40"


class FacturaPage(BasePage):

    def navigate(self, url: str):
        """Navega al formulario de factura CFDI 4.0.

        Estrategia de dos vías:
          1. Si ya estamos en la página de factura → clic en el ítem del menú lateral.
             JSF hace un POST/GET al mismo recurso manteniendo la sesión y reutilizando
             los recursos estáticos del caché de Chrome → más rápido que driver.get().
          2. Si estamos en otra página → driver.get(url) (carga completa inicial).

        En ambos casos espera a que el formulario esté completamente renderizado
        antes de devolver el control al test.
        """
        t0 = time.time()
        current = self.driver.current_url

        if _FACTURA_URL_FRAGMENT in current:
            # Ya estamos en la página de factura → navegar vía menú para evitar
            # un reload completo y aprovechar el caché de recursos estáticos.
            log.info("Already on factura page — navigating via sidebar menu link")
            try:
                menu_link = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, _MENU_FACTURA40_CSS))
                )
                menu_link.click()
                log.info("  Menu click done (%.1fs)", time.time() - t0)
            except Exception as exc:
                log.warning("  Menu click failed (%s) — falling back to driver.get()", exc)
                self.driver.get(url)
        else:
            log.info("Navigating to factura form (full load): %s", url)
            self.driver.get(url)
            log.info("  driver.get done (%.1fs)", time.time() - t0)

        wait_for_ajax(self.driver)
        log.info("CFDI form loaded — total navigate time: %.1fs", time.time() - t0)

    # ── Emisor ──────────────────────────────────────────────────────────────

    def fill_emisor(self, rfc: str, sucursal: str, cc: str):
        log.info("Filling Emisor: rfc=%s sucursal=%s cc=%s", rfc, sucursal, cc)
        # RFC dropdown with filter
        trigger = wait_for_element_clickable(self.driver, By.ID, _EMISOR_SELECT)
        trigger.click()
        wait_for_ajax(self.driver)

        # Use filter input to narrow the list
        try:
            filter_el = self.driver.find_element(By.ID, _EMISOR_FILTER)
            filter_el.clear()
            filter_el.send_keys(rfc)
            wait_for_ajax(self.driver)
        except Exception:
            pass

        panel = wait_for_element_visible(self.driver, By.ID, _EMISOR_SELECT + "_panel")
        items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")
        for item in items:
            if rfc in item.text:
                item.click()
                wait_for_ajax(self.driver)
                log.debug("Emisor RFC selected: %s", rfc)
                break
        else:
            raise ValueError(f"RFC Emisor '{rfc}' not found in dropdown")

        # Sucursal (appears after Emisor selection via AJAX)
        self.select_one_menu_contains(_SUCURSAL_SELECT, sucursal)

        # Wait for any PrimeFaces blockUI overlay to disappear before continuing.
        # Selecting Sucursal fires an AJAX call that briefly shows j_idt34_modal
        # (ui-widget-overlay ui-dialog-mask).  Clicking CC while it is visible
        # raises "element click intercepted" on the overlay div.
        try:
            WebDriverWait(self.driver, 15).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, "div.ui-widget-overlay.ui-dialog-mask")
                )
            )
        except Exception:
            pass  # overlay not present or already gone — safe to continue

        # Centro de Consumo
        self.select_one_menu_exact(_CC_SELECT, cc)

    # ── Receptor ────────────────────────────────────────────────────────────

    def fill_receptor(self, rfc: str, nombre: str, uso_cfdi: str, regimen: str,
                      domicilio_cp: str, email: str):
        log.info("Filling Receptor: rfc=%s", rfc)

        # 1. Type RFC + TAB → triggers onblur AJAX auto-fill
        rfc_el = wait_for_element_clickable(self.driver, By.ID, _RFC_RECEPTOR)
        rfc_el.clear()
        rfc_el.send_keys(rfc)
        rfc_el.send_keys(Keys.TAB)
        log.info("TAB pressed — waiting for receptor fields autofill via AJAX")
        wait_for_ajax(self.driver)

        # 2. Wait until Uso de CFDI label is populated (confirms AJAX finished)
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: d.find_element(By.ID, _USO_CFDI + "_label")
                           .get_attribute("textContent").strip()
                          not in ("", "Uso de CFDI *")
            )
            log.info("Receptor fields auto-filled by AJAX")
        except Exception:
            log.warning("Uso CFDI label did not populate within 15 s — filling fields manually")

        # 3. Reinforce — verify each field and fill manually if still empty

        # Nombre
        log.info("[fill_receptor] Forzando campo: Nombre → %s", nombre)
        try:
            nom_val = (
                self.driver.find_element(By.ID, _NOMBRE_RECEPTOR)
                .get_attribute("value") or ""
            ).strip()
            if not nom_val:
                self.force_input(_NOMBRE_RECEPTOR, nombre)
            else:
                log.debug("Nombre auto-filled: '%s'", nom_val)
        except Exception as _e:
            log.warning("Nombre field not interactable: %s", _e)

        # Uso CFDI
        log.info("[fill_receptor] Forzando campo: Uso CFDI → %s", uso_cfdi)
        try:
            uso_txt = (
                self.driver.find_element(By.ID, _USO_CFDI + "_label")
                .get_attribute("textContent") or ""
            ).strip()
            if not uso_txt or uso_txt in ("Uso de CFDI *", "Seleccione"):
                log.warning("[fill_receptor] Uso CFDI no auto-llenado ('%s') — forzando: %s", uso_txt, uso_cfdi)
                self.force_jquery(_USO_CFDI + "_input", uso_cfdi)
            else:
                log.debug("Uso CFDI auto-filled: '%s'", uso_txt)
        except Exception as _e:
            log.warning("Uso CFDI field not interactable: %s", _e)

        # Régimen Fiscal Receptor
        log.info("[fill_receptor] Forzando campo: Régimen → %s", regimen)
        try:
            reg_txt = (
                self.driver.find_element(By.ID, _REGIMEN_RECEPTOR + "_label")
                .get_attribute("textContent") or ""
            ).strip()
            if not reg_txt or reg_txt in ("Régimen Fiscal Receptor *", "Seleccione"):
                log.warning("[fill_receptor] Régimen no auto-llenado ('%s') — forzando: %s", reg_txt, regimen)
                self.force_jquery(_REGIMEN_RECEPTOR + "_input", regimen)
            else:
                log.debug("Regimen auto-filled: '%s'", reg_txt)
        except Exception as _e:
            log.warning("Regimen field not interactable: %s", _e)

        # Domicilio Fiscal CP
        log.info("[fill_receptor] Forzando campo: Domicilio CP → %s", domicilio_cp)
        try:
            dom_val = (
                self.driver.find_element(By.ID, _DOMICILIO_RECEPTOR)
                .get_attribute("value") or ""
            ).strip()
            if not dom_val:
                self.force_input(_DOMICILIO_RECEPTOR, domicilio_cp)
            else:
                log.debug("Domicilio CP auto-filled: '%s'", dom_val)
        except Exception as _e:
            log.warning("Domicilio CP field not interactable: %s", _e)

        # Email
        try:
            email_input = self.driver.find_element(By.ID, _EMAIL_RECEPTOR + "_input")
            email_input.clear()
            email_input.send_keys(email)
        except Exception:
            log.warning("Email field not found, skipping")

        # ── RFC re-verificación (siempre al final) ────────────────────────────
        # El AJAX de auto-fill de PrimeFaces puede vaciar el campo RFC como parte
        # de su respuesta (re-render parcial del form).  Se confirma y re-llena
        # DESPUÉS de todos los demás campos para que sea el último valor escrito.
        try:
            rfc_val = (
                self.driver.find_element(By.ID, _RFC_RECEPTOR)
                .get_attribute("value") or ""
            ).strip()
            if rfc.upper() not in rfc_val.upper():
                log.warning(
                    "RFC Receptor vacío o incorrecto ('%s') tras auto-fill — re-llenando: %s",
                    rfc_val, rfc,
                )
                rfc_el2 = wait_for_element_clickable(self.driver, By.ID, _RFC_RECEPTOR)
                rfc_el2.clear()
                rfc_el2.send_keys(rfc)
                wait_for_ajax(self.driver)
                # Si send_keys no persistó (AJAX tardío sobrescribió el DOM)
                # usar JS como fallback definitivo
                rfc_post = (
                    self.driver.find_element(By.ID, _RFC_RECEPTOR)
                    .get_attribute("value") or ""
                ).strip()
                if rfc.upper() not in rfc_post.upper():
                    log.warning(
                        "send_keys no persistó (AJAX tardió) — forzando RFC via JS"
                    )
                    self.driver.execute_script(
                        "var el = document.getElementById(arguments[0]);"
                        "if (el) {"
                        "  el.removeAttribute('readonly'); el.removeAttribute('disabled');"
                        "  el.value = arguments[1];"
                        "  window.jQuery(el).trigger('input').trigger('change').trigger('blur');"
                        "}",
                        _RFC_RECEPTOR, rfc,
                    )
                    wait_for_ajax(self.driver)
                rfc_final = (
                    self.driver.find_element(By.ID, _RFC_RECEPTOR)
                    .get_attribute("value") or ""
                ).strip()
                log.info("RFC Receptor re-llenado — valor final: '%s'", rfc_final)
                if rfc.upper() not in rfc_final.upper():
                    raise RuntimeError(
                        f"RFC Receptor '{rfc}' no pudo ser confirmado en el DOM "
                        f"(valor final: '{rfc_final}'). El flujo no puede continuar sin RFC."
                    )
            else:
                log.debug("RFC Receptor confirmado: '%s'", rfc_val)
        except RuntimeError:
            raise
        except Exception as _e:
            log.warning("RFC Receptor verificación falló: %s", _e)

    # ── Comprobante ─────────────────────────────────────────────────────────

    def _select_tipo_comprobante(self, tipo: str):
        """Select Tipo de Comprobante.

        Estrategias de apertura del panel (en orden):
          1. Selenium click en .ui-selectonemenu-trigger
          2. JS click en .ui-selectonemenu-trigger
          3. PrimeFaces widget API: PF(widgetVar).show()
          4. Selenium click en el _label (texto visible del campo)
        Si ninguna abre el panel → fallback JS directo sobre <select> nativo.
        """
        widget_id = _TIPO_COMPROBANTE
        label_id  = _TIPO_COMPROBANTE_LABEL
        panel_id  = widget_id + "_panel"
        target    = tipo.strip().lower()

        # ── helper: intenta abrir el panel con la estrategia N ─────────────────
        def _open_panel_strategy(n: int) -> "WebElement | None":
            """Ejecuta la estrategia N para abrir el panel. Devuelve el panel visible o None."""
            try:
                if n == 0:
                    # Estrategia 1 — Selenium click en el botón de la flechita
                    container = wait_for_element_present(self.driver, By.ID, widget_id)
                    btn = container.find_element(By.CSS_SELECTOR, ".ui-selectonemenu-trigger")
                    self.scroll_to(btn)
                    btn.click()

                elif n == 1:
                    # Estrategia 2 — JS click en el botón de la flechita
                    self.driver.execute_script(
                        "var el = document.getElementById(arguments[0]);"
                        "if (el) {"
                        "  var btn = el.querySelector('.ui-selectonemenu-trigger');"
                        "  if (btn) btn.click();"
                        "}",
                        widget_id,
                    )

                elif n == 2:
                    # Estrategia 3 — PrimeFaces widget API
                    self.driver.execute_script(
                        "try {"
                        "  var wv = arguments[0].replace(/:/g,'_');"
                        "  if (window.PrimeFaces) PF(wv).show();"
                        "} catch(e) {}",
                        widget_id,
                    )

                elif n == 3:
                    # Estrategia 4 — click en el label visible del combo
                    lbl = wait_for_element_clickable(self.driver, By.ID, label_id, timeout=6)
                    self.scroll_to(lbl)
                    lbl.click()

            except Exception as _open_err:
                log.debug("Estrategia %d para abrir panel falló: %s", n + 1, _open_err)

            # Dar tiempo a PrimeFaces para renderizar el panel
            time.sleep(0.5)
            wait_for_ajax(self.driver)

            # Buscar panel por ID
            try:
                p = wait_for_element_visible(self.driver, By.ID, panel_id, timeout=10)
                log.debug("Panel abierto con estrategia %d (por ID)", n + 1)
                return p
            except Exception:
                pass

            # Fallback CSS: cualquier panel de selectonemenu visible
            all_panels = self.driver.find_elements(By.CSS_SELECTOR, "div.ui-selectonemenu-panel")
            visible = [p for p in all_panels if p.is_displayed()]
            if visible:
                log.debug("Panel abierto con estrategia %d (por CSS)", n + 1)
                return visible[-1]

            return None

        # ── helper: fallback JS directo sobre <select> nativo ──────────────────
        def _force_via_native_select() -> bool:
            """Selecciona la opción directamente en el <select> subyacente via JS."""
            try:
                result = self.driver.execute_script(
                    "var sel = document.getElementById(arguments[0]);"
                    "if (!sel) {"
                    "  var els = document.querySelectorAll('select');"
                    "  for (var s=0; s<els.length; s++) {"
                    "    if (els[s].id && els[s].id.indexOf('TipoComprobante') !== -1) {"
                    "      sel = els[s]; break;"
                    "    }"
                    "  }"
                    "}"
                    "if (!sel || sel.tagName !== 'SELECT') return 'no-select';"
                    "var tgt = arguments[1].toLowerCase();"
                    "for (var i = 0; i < sel.options.length; i++) {"
                    "  if (sel.options[i].text.toLowerCase().indexOf(tgt) !== -1) {"
                    "    sel.selectedIndex = i;"
                    "    var ev = new Event('change', {bubbles:true});"
                    "    sel.dispatchEvent(ev);"
                    "    if (window.jQuery) window.jQuery(sel).trigger('change');"
                    "    return 'ok:' + sel.options[i].text;"
                    "  }"
                    "}"
                    "var opts = [];"
                    "for (var j=0; j<sel.options.length; j++) opts.push(sel.options[j].text);"
                    "return 'not-found:' + opts.join('|');",
                    widget_id,
                    target,
                )
                log.info("Fallback <select> nativo resultado: %s", result)
                if isinstance(result, str) and result.startswith("ok:"):
                    return True
                return False
            except Exception as _js_err:
                log.warning("Fallback <select> nativo excepción: %s", _js_err)
                return False

        # ── bucle principal (3 reintentos por StaleElement) ────────────────────
        for attempt in range(3):
            try:
                # Descartar overlay modal bloqueante antes de interactuar
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located(
                            (By.CSS_SELECTOR, "div.ui-widget-overlay.ui-dialog-mask")
                        )
                    )
                except Exception:
                    pass

                # Probar las 4 estrategias de apertura en cascada
                panel = None
                for strat in range(4):
                    panel = _open_panel_strategy(strat)
                    if panel is not None:
                        break
                    log.warning(
                        "Tipo Comprobante: estrategia %d no encontró panel (attempt %d/3)",
                        strat + 1, attempt + 1,
                    )

                if panel is None:
                    # ── Todas las estrategias fallaron — JS directo ──────────
                    log.warning(
                        "Panel no visible tras 4 estrategias — forzando via <select> nativo"
                        " (attempt %d/3)", attempt + 1,
                    )
                    if _force_via_native_select():
                        wait_for_ajax(self.driver)
                        time.sleep(0.3)
                        try:
                            valor_final = self.driver.find_element(By.ID, label_id).text.strip()
                        except Exception:
                            valor_final = tipo
                        log.info("Tipo comprobante forzado via JS: '%s'", valor_final)
                        return

                    if attempt == 2:
                        raise RuntimeError(
                            f"_select_tipo_comprobante: panel no visible y JS directo falló "
                            f"para '{tipo}' tras 3 intentos"
                        )
                    log.warning("JS directo falló en attempt %d — reintentando toda la secuencia", attempt + 1)
                    wait_for_ajax(self.driver)
                    time.sleep(1.0)
                    continue

                # Panel encontrado — leer ítems
                items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")
                if not items:
                    raise ValueError(
                        f"_select_tipo_comprobante: panel '{panel_id}' sin ítems"
                    )

                for item in items:
                    texto = item.text.strip()
                    if target in texto.lower():
                        self.scroll_to(item)
                        try:
                            item.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", item)

                        wait_for_ajax(self.driver)

                        try:
                            valor_final = self.driver.find_element(By.ID, label_id).text.strip()
                        except Exception:
                            valor_final = texto

                        if not valor_final or target not in valor_final.lower():
                            raise ValueError(
                                f"Tipo comprobante: clicked '{texto}' pero "
                                f"_label muestra '{valor_final}' (esperado '{tipo}')"
                            )

                        log.info("Tipo comprobante seleccionado: '%s'", valor_final)
                        return

                opciones = [i.text.strip() for i in items if i.text.strip()]
                raise ValueError(
                    f"_select_tipo_comprobante: '{tipo}' no encontrado. Disponibles: {opciones}"
                )

            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                log.warning(
                    "StaleElement en _select_tipo_comprobante (attempt %d/3) — retrying…",
                    attempt + 1,
                )
                wait_for_ajax(self.driver)


    def fill_comprobante(self, tipo: str, serie: str, forma_pago: str,
                         metodo_pago: str, moneda: str, tipo_cambio: float = 0.0):
        log.info("Filling Comprobante: tipo=%s serie=%s forma=%s", tipo, serie, forma_pago)
        self._select_tipo_comprobante(tipo)

        # Dar tiempo al AJAX de re-render que PrimeFaces dispara tras elegir
        # Tipo Comprobante (reconstruye el panel Comprobante; sin esta espera
        # la Serie puede estar momentáneamente no-clickable).
        wait_for_ajax(self.driver)
        time.sleep(1.0)

        # ── Serie ── force con validación DOM + reintentos automáticos
        log.info("Seleccionando Serie: %s", serie)
        self.force_select_contains(_SERIE, serie)

        # ── Forma de Pago ── force jQuery con label visible + retry
        log.info("Seleccionando Forma de Pago: %s", forma_pago)
        self.force_jquery(_FORMA_PAGO + "_input", forma_pago)

        # ── Método de Pago ── force jQuery con label visible + retry
        log.info("Seleccionando Método de Pago: %s", metodo_pago)
        self.force_jquery(_METODO_PAGO + "_input", metodo_pago)

        self.fill_moneda(moneda)
        if tipo_cambio > 0:
            self.fill_tipo_cambio_ppd(tipo_cambio)

    def fill_tipo_cambio_ppd(self, tipo_cambio: float):
        """Fill 'Tipo de Cambio' field on the PPD factura form (visible when moneda ≠ MXN).

        Rendered inside panelGroupTipoCambio after AJAX refresh on moneda change.
        Uses JS fallback if the field is still disabled/not interactable.
        """
        import time as _t
        log.info("fill_tipo_cambio_ppd: %.4f", tipo_cambio)
        wait_for_ajax(self.driver)
        _t.sleep(0.3)
        valor_str = str(tipo_cambio)
        try:
            el = wait_for_element_clickable(
                self.driver, By.ID, _INPUT_TIPO_CAMBIO, timeout=10
            )
            el.clear()
            el.send_keys(valor_str)
            wait_for_ajax(self.driver)
        except Exception:
            log.warning("fill_tipo_cambio_ppd: Selenium interaction failed — using JS fallback")
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
                _INPUT_TIPO_CAMBIO, valor_str,
            )
            wait_for_ajax(self.driver)

    def fill_moneda(self, moneda: str, max_attempts: int = 3):
        """Fill Moneda PrimeFaces autocomplete con retry + validación DOM.

        Estrategia por intento:
          1. Limpiar → escribir el código → esperar panel.
          2. Clic en el primer ítem que contenga el código.
          3. Fallback: ARROW_DOWN + ENTER si el panel no apareció.
          4. Confirmar leyendo get_attribute("value").
          5. Si no coincide → reintentar; después de max_attempts → FieldFillError.
        """
        from utils.force_helpers import FieldFillError
        log.info("Filling Moneda: %s", moneda)
        _PANEL_ITEM_CSS = "ul.ui-autocomplete-items li.ui-autocomplete-item"

        for attempt in range(1, max_attempts + 1):
            campo = wait_for_element_clickable(self.driver, By.ID, _MONEDA_AC, timeout=10)
            self.scroll_to(campo)

            self.driver.execute_script("arguments[0].value = '';", campo)
            campo.send_keys(Keys.CONTROL, "a")
            campo.send_keys(Keys.BACKSPACE)
            time.sleep(0.1)

            campo.send_keys(moneda)
            time.sleep(0.35)

            try:
                items = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, _PANEL_ITEM_CSS)
                    )
                )
                target_item = None
                for item in items:
                    if moneda.upper() in (item.text or "").upper():
                        target_item = item
                        break
                if target_item is None:
                    target_item = items[0]
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'nearest'});", target_item
                )
                target_item.click()
                wait_for_ajax(self.driver)
            except Exception:
                campo.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.15)
                campo.send_keys(Keys.ENTER)
                time.sleep(0.2)
                wait_for_ajax(self.driver)

            try:
                campo = self.driver.find_element(By.ID, _MONEDA_AC)
                valor_final = (campo.get_attribute("value") or "").strip()
            except Exception:
                valor_final = ""

            if moneda.upper() in valor_final.upper():
                if attempt > 1:
                    log.info("Moneda confirmada en intento %d: '%s'", attempt, valor_final)
                else:
                    log.info("Moneda final capturada en input: '%s'", valor_final)
                return

            log.warning(
                "Moneda '%s' no confirmada (intento %d/%d), valor actual: '%s' — reintentando",
                moneda, attempt, max_attempts, valor_final,
            )
            # Intentar TAB para que PrimeFaces dispare itemSelect via blur
            try:
                campo = self.driver.find_element(By.ID, _MONEDA_AC)
                campo.send_keys(Keys.TAB)
                wait_for_ajax(self.driver)
                valor_post_tab = (
                    self.driver.find_element(By.ID, _MONEDA_AC)
                    .get_attribute("value") or ""
                ).strip()
                if moneda.upper() in valor_post_tab.upper():
                    log.info("Moneda confirmada tras TAB: '%s'", valor_post_tab)
                    return
            except Exception:
                pass
            wait_for_ajax(self.driver)

        raise FieldFillError(
            f"Moneda '{moneda}' no quedó confirmada en el DOM "
            f"después de {max_attempts} intentos."
        )


    def expandir_impuestos(self):
        log.info("[expandir_impuestos] Buscando el fieldset de Impuestos...")

        # 1. Esperar a que el fieldset exista en el DOM
        fieldset = wait_for_element_present(
            self.driver,
            By.CSS_SELECTOR,
            _FIELDSET_IMPUESTOS_CSS,
            timeout=15,
        )

        # 2. Scroll agresivo: centrar el fieldset en pantalla y luego bajar un poco más
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            fieldset,
        )
        # Empujar hacia abajo para que el legend '+' quede visible sobre el pliegue
        self.driver.execute_script("window.scrollBy(0, 150);")

        # 3. Localizar el botón '+' (legend > span del fieldset)
        log.info("[expandir_impuestos] Esperando botón '+' de Impuestos...")
        btn = wait_for_element_clickable(
            self.driver,
            By.CSS_SELECTOR,
            _BTN_EXPANDIR_IMPUESTOS_CSS,
            timeout=10,
        )

        # 4. Verificar si ya está expandido — skip click si el campo Impuesto
        #    es realmente visible (offsetHeight > 0 considera el padre display:none).
        ya_abierto = self.driver.execute_script(
            "var el = document.getElementById(arguments[0]);"
            "if (!el) return false;"
            "return el.offsetHeight > 0;",
            _SEL_IMPUESTO,
        )
        if ya_abierto:
            log.info("[expandir_impuestos] Módulo ya estaba abierto — sin clic.")
            return

        # Scroll al botón '+' y click (JS como fallback)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            btn,
        )
        log.info("[expandir_impuestos] Dando clic en el botón '+' para expandir...")
        try:
            btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn)

        wait_for_ajax(self.driver)

        # 5. Confirmar que el sub-formulario de impuestos esté visible
        wait_for_element_present(self.driver, By.ID, _SEL_IMPUESTO, timeout=10)
        log.info("[expandir_impuestos] Módulo de impuestos expandido y listo.")



    
    # ── Conceptos ───────────────────────────────────────────────────────────

    def add_concepto(self, concepto: ConceptoRow, impuestos: List[ImpuestoRow]):
        """Agrega un concepto completo al formulario.

        Flujo garantizado:
          1  Cantidad
          2  Clave Unidad
          3  Descripción
          4  Clave Producto / Servicio
          5  Valor Unitario
          6  Objeto Impuesto  (seleccionar valor que empieza con '02' si aplica)
          7  Si Objeto Impuesto = 02:
               a. Expandir módulo de impuestos
               b. Agregar TODOS los impuestos relacionados
          8  Clic en Agregar Concepto
          9  Scroll al panel de botones de facturación
        """
        log.info(
            "─── add_concepto INICIO  id=%d | desc=%s | objeto_imp=%s",
            concepto.id_concepto,
            concepto.descripcion,
            concepto.objeto_impuesto,
        )

        # ── Paso 1: Cantidad ─────────────────────────────────────────────────
        cantidad_str = (
            str(int(concepto.cantidad))
            if concepto.cantidad == int(concepto.cantidad)
            else str(concepto.cantidad)
        )
        log.info("[Paso 1] Cantidad: %s", cantidad_str)
        self._clear_and_type(_INPUT_CANTIDAD, cantidad_str)
        wait_for_ajax(self.driver)

        # ── Paso 2: Clave Unidad ─────────────────────────────────────────────
        log.info("[Paso 2] Clave Unidad: %s", concepto.clave_unidad)
        self.autocomplete(_AC_CLAVE_UNIDAD, concepto.clave_unidad, concepto.clave_unidad)
        wait_for_ajax(self.driver)

        # ── Paso 3: Descripción ──────────────────────────────────────────────
        log.info("[Paso 3] Descripción: %s", concepto.descripcion)
        self.autocomplete(_AC_DESCRIPCION, concepto.descripcion, concepto.descripcion.strip())
        wait_for_ajax(self.driver)

        # ── Paso 4: Clave Producto / Servicio ────────────────────────────────
        log.info("[Paso 4] Clave Producto: %s", concepto.clave_producto)
        self.autocomplete(_AC_CLAVE_PROD, concepto.clave_producto, concepto.clave_producto)
        wait_for_ajax(self.driver)

        # ── Paso 5: Valor Unitario ───────────────────────────────────────────
        log.info("[Paso 5] Valor Unitario: %s", concepto.valor_unitario)
        self._clear_and_type(_INPUT_VALOR_UNIT, str(concepto.valor_unitario))
        wait_for_ajax(self.driver)

        # ── Paso 6: Objeto Impuesto ──────────────────────────────────────────
        log.info("[Paso 6] Objeto Impuesto: %s", concepto.objeto_impuesto)
        self.select_one_menu_contains(_OBJETO_IMP, concepto.objeto_impuesto)
        wait_for_ajax(self.driver)
        time.sleep(0.5)  # dar tiempo al DOM para mostrar/ocultar el fieldset de impuestos

        # ── Paso 7: Impuestos — SIEMPRE se ejecuta ───────────────────────────
        objeto_imp_str = str(concepto.objeto_impuesto).strip()

        # Filtrar impuestos del concepto actual (sin condición sobre objeto_imp)
        impuestos_relacionados = [
            imp for imp in impuestos
            if imp.id_concepto == concepto.id_concepto
        ]

        # Regla de negocio: si objeto_imp = 02 y no hay impuestos → error
        if objeto_imp_str.startswith("02") and not impuestos_relacionados:
            raise ValueError(
                f"Concepto id={concepto.id_concepto} ('{concepto.descripcion}') "
                f"tiene Objeto Impuesto='{objeto_imp_str}' (requiere impuestos), "
                "pero no se encontraron impuestos relacionados en el Excel."
            )

        if impuestos_relacionados:
            log.info(
                "[Paso 7] Agregando %d impuesto(s) para concepto id=%d "
                "(Objeto Imp='%s')...",
                len(impuestos_relacionados),
                concepto.id_concepto,
                objeto_imp_str,
            )

            # 7a. Expandir el módulo de impuestos (botón "+")
            log.info("[Paso 7a] Expandiendo módulo de impuestos...")
            self.expandir_impuestos()
            wait_for_ajax(self.driver)

            # 7b. Capturar cada impuesto antes de agregar el concepto
            for idx, imp in enumerate(impuestos_relacionados, start=1):
                log.info(
                    "[Paso 7b.%d/%d] Impuesto: clave=%s | local_fed=%s | ret_tras=%s | factor=%s | tasa=%s",
                    idx,
                    len(impuestos_relacionados),
                    imp.clave_impuesto,
                    imp.local_federal,
                    imp.retencion_traslado,
                    imp.tipo_factor,
                    imp.tasa_cuota,
                )
                self._add_impuesto(imp)
                wait_for_ajax(self.driver)
                time.sleep(0.2)

            log.info(
                "[Paso 7] Todos los impuestos del concepto id=%d capturados.",
                concepto.id_concepto,
            )

        else:
            log.info(
                "[Paso 7] Sin impuestos asociados para concepto id=%d "
                "(Objeto Imp='%s') — se omite expansión.",
                concepto.id_concepto,
                objeto_imp_str,
            )

        # ── Paso 8: Agregar Concepto ─────────────────────────────────────────
        # IMPORTANTE: este clic se ejecuta SIEMPRE después de los impuestos
        log.info("[INFO] Click botón verde Agregar concepto (id=%d)", concepto.id_concepto)
        self.safe_click(_BTN_AGREGAR_CONC)
        wait_for_ajax(self.driver)
        time.sleep(0.5)
        log.info("[Paso 8] Concepto id=%d agregado exitosamente.", concepto.id_concepto)

        # ── Paso 9: Scroll al panel de botones de facturación ────────────────
        log.info("[Paso 9] Scroll al panel de botones de facturación.")
        try:
            panel_botones = wait_for_element_present(
                self.driver,
                By.ID,
                _PANEL_BOTONES,
                timeout=10,
            )
            self.scroll_to(panel_botones)
        except Exception:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.3)

        log.info("─── add_concepto FIN  id=%d", concepto.id_concepto)


 
    def _count_impuesto_rows(self) -> int:
        """Cuenta el total de impuestos registrados (traslados + retenciones).

        Usa el API del widget PrimeFaces para obtener el rowCount real del servidor
        (cubre paginación y posibles tablas separadas por tipo de impuesto).
        Como fallback cuenta las filas visibles en cualquier tabla dentro del fieldset.
        """
        try:
            count = self.driver.execute_script(
                """
                // Intento 1: rowCount del widget PrimeFaces (total verdadero,
                // incluve filas en páginas no visibles del paginador)
                for (var k in PrimeFaces.widgets) {
                    var w = PrimeFaces.widgets[k];
                    if (w && w.id &&
                        w.id.indexOf('dataTableImpuestosConcepto') >= 0 &&
                        w.paginator &&
                        typeof w.paginator.cfg === 'object' &&
                        typeof w.paginator.cfg.rowCount === 'number') {
                        return w.paginator.cfg.rowCount;
                    }
                }
                // Intento 2: contar filas visibles en TODAS las tablas del fieldset
                // (cubre el caso de tablas separadas por Traslado/Retención)
                var fs = document.getElementById(
                    'formNuevaFactura:accordionConceptos:filedSetImpuestos'
                );
                if (!fs) return 0;
                var rows = fs.querySelectorAll('[id$="_data"] tr');
                var n = 0;
                for (var i = 0; i < rows.length; i++) {
                    if (rows[i].className.indexOf('ui-datatable-empty-message') < 0) {
                        n++;
                    }
                }
                return n;
                """
            )
            return int(count) if count is not None else 0
        except Exception:
            return 0

    def _read_select_value_text(self, select_id: str) -> str:
        """Lee el texto de la opción actualmente seleccionada en un hidden <select>."""
        try:
            return self.driver.execute_script(
                "var s = document.getElementById(arguments[0]);"
                "if (!s) return '?';"
                "var v = s.value;"
                "var o = Array.from(s.options).find(function(x){return x.value===v;});"
                "return o ? o.text.trim() : '(value='+v+')'",
                select_id,
            ) or ""
        except Exception:
            return "?"

    def _list_select_options(self, select_id: str) -> list:
        """Devuelve ['texto=valor', ...] para todas las opciones de un <select>."""
        try:
            return self.driver.execute_script(
                "var s=document.getElementById(arguments[0]);"
                "return s ? Array.from(s.options).map(function(o){"
                "  return o.text.trim()+'='+o.value; }) : ['NOT FOUND'];",
                select_id,
            ) or []
        except Exception:
            return ["ERROR"]

    def _pf_select_by_ui(
        self,
        component_base_id: str,
        expected_value: str,
        field_name: str = "",
        max_retries: int = 3,
        timeout: int = 8,
    ) -> str:
        """Selects an option in a PrimeFaces SelectOneMenu by simulating real user click.

        Unlike force_jquery (which only sets the hidden <select> via JS and fires change),
        this method clicks the dropdown trigger, waits for the overlay panel, and clicks
        the matching item. This runs PrimeFaces's own widget JS, which:
          1. Updates the _label span (visual widget)
          2. Updates the hidden <select>
          3. Fires the proper PrimeFaces partial submit (AJAX) → JSF ViewState updated

        Args:
            component_base_id: Base ID WITHOUT '_input' suffix.
                               E.g. "formNuevaFactura:accordionConceptos:selectOneImpuestosLocalFederal"
            expected_value:    Text to select (e.g. "FEDERAL", "TRASLADO").
            field_name:        Human-readable name for logs.
            max_retries:       Retries if selection not confirmed (default 3).
            timeout:           Wait timeout in seconds for panel/item.

        Returns:
            Confirmed _label text.

        Raises:
            RuntimeError if label does not match after max_retries attempts.
        """
        import unicodedata as _ucd

        def _n(s: str) -> str:
            return ''.join(
                c for c in _ucd.normalize('NFD', str(s).lower())
                if _ucd.category(c) != 'Mn'
            )

        name      = field_name or component_base_id
        target_n  = _n(expected_value)
        css_id    = component_base_id.replace(':', r'\:')
        label_id  = component_base_id + "_label"
        panel_id  = component_base_id + "_panel"

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                log.warning("[_pf_select_by_ui] '%s' reintento %d/%d", name, attempt, max_retries)

            # 1. Scroll the trigger into view and click it to open the overlay
            try:
                trigger = self.driver.find_element(
                    By.CSS_SELECTOR,
                    f"#{css_id} .ui-selectonemenu-trigger",
                )
            except Exception:
                # Fallback: click the label container itself
                trigger = self.driver.find_element(
                    By.CSS_SELECTOR,
                    f"#{css_id} .ui-selectonemenu-label-container",
                )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', behavior:'instant'});", trigger
            )
            time.sleep(0.1)
            try:
                trigger.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", trigger)

            # 2. Wait for the overlay panel to be visible
            try:
                panel = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.ID, panel_id))
                )
            except Exception:
                log.warning(
                    "[_pf_select_by_ui] '%s' overlay panel '%s' no apareció (intento %d/%d)",
                    name, panel_id, attempt, max_retries,
                )
                wait_for_ajax(self.driver)
                continue

            # 3. Find the matching item inside the panel
            items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")
            available = []
            matched = None
            for item in items:
                text = (item.get_attribute("data-label") or item.text or "").strip()
                available.append(text)
                t_n = _n(text)
                if matched is None and (t_n == target_n or t_n.startswith(target_n)):
                    matched = item
            # Fallback: contains (avoid matching placeholders — only if nothing else found)
            if matched is None:
                for item in items:
                    text = (item.get_attribute("data-label") or item.text or "").strip()
                    if text and target_n in _n(text) and _n(text) != _n(expected_value.lower() + " "):
                        # Skip option if it looks like the placeholder (e.g. "Local o Federal")
                        # by requiring the text is NOT longer than twice the target
                        if len(text) <= len(expected_value) * 2 + 4:
                            matched = item
                            break

            if matched is None:
                log.warning(
                    "[_pf_select_by_ui] '%s' opciones disponibles: %s — '%s' no encontrado (intento %d/%d)",
                    name, available, expected_value, attempt, max_retries,
                )
                # Close panel by pressing Escape
                try:
                    from selenium.webdriver.common.keys import Keys as _Keys
                    panel.send_keys(_Keys.ESCAPE)
                except Exception:
                    pass
                wait_for_ajax(self.driver)
                continue

            # 4. Click the matching item
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'nearest'});", matched
            )
            time.sleep(0.05)
            try:
                matched.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", matched)

            wait_for_ajax(self.driver)
            time.sleep(0.15)

            # 5. Verify the _label was updated (exact or starts-with — NOT substring of placeholder)
            try:
                label_text = self.driver.find_element(By.ID, label_id).text.strip()
            except Exception:
                label_text = ""

            label_n = _n(label_text)
            if label_n == target_n or label_n.startswith(target_n):
                log.info(
                    "[_pf_select_by_ui] '%s' confirmado en _label (intento %d/%d): '%s'",
                    name, attempt, max_retries, label_text,
                )
                return label_text

            log.warning(
                "[_pf_select_by_ui] '%s' _label='%s' no coincide con '%s' (intento %d/%d)",
                name, label_text, expected_value, attempt, max_retries,
            )
            wait_for_ajax(self.driver)

        raise RuntimeError(
            f"[_add_impuesto] No se pudo seleccionar '{expected_value}' en '{name}' "
            f"después de {max_retries} intentos vía UI click. "
            f"Verifica que el panel del dropdown sea visible y que la opción exista."
        )

    def _set_selects_no_ajax(self, fields: list) -> list:
        """Asigna valores a varios hidden <select> en una sola llamada JS sin disparar AJAX.

        Args:
            fields: lista de (select_id, label_to_match) — match por contains, insensible a may.
        Returns:
            Lista de mensajes de error (vacía si todo fue bien).
        """
        ids     = [f[0] for f in fields]
        labels  = [f[1] for f in fields]
        errors = self.driver.execute_script(
            """
            var ids    = arguments[0];
            var labels = arguments[1];
            var errs   = [];
            for (var i = 0; i < ids.length; i++) {
                var sel = document.getElementById(ids[i]);
                if (!sel) { errs.push('NOT FOUND: ' + ids[i]); continue; }
                var t = labels[i].trim().toLowerCase();
                var opts = Array.from(sel.options);
                var found = null;
                // Priority 1: exact match
                for (var a = 0; a < opts.length; a++) {
                    if (opts[a].text.trim().toLowerCase() === t) { found = opts[a]; break; }
                }
                // Priority 2: starts-with
                if (!found) for (var b = 0; b < opts.length; b++) {
                    if (opts[b].text.trim().toLowerCase().indexOf(t) === 0) { found = opts[b]; break; }
                }
                // Priority 3: contains (fallback — last resort to avoid matching placeholders)
                if (!found) for (var c = 0; c < opts.length; c++) {
                    if (opts[c].text.trim().toLowerCase().indexOf(t) >= 0) { found = opts[c]; break; }
                }
                if (found) {
                    sel.value = found.value;
                } else {
                    errs.push('OPTION NOT FOUND: "' + labels[i] + '" in ' + ids[i]
                        + ' [' + opts.map(function(o){return o.text.trim();}).join(' | ') + ']');
                }
            }
            return errs;
            """,
            ids, labels,
        )
        return errors or []

    def _add_impuesto(self, imp: ImpuestoRow):
        """Llena el sub-formulario de impuesto en el orden real de la UI y verifica la fila.

        Orden de llenado (igual que en la UI):
          1. Impuesto        (force_jquery → AJAX cascada)
          2. Tipo Factor     (force_jquery → AJAX cascada)
          3. Local o Federal (DOM directo — evita validación de CFDI Relacionado)
          4. Retención o Traslado (DOM directo)
          5. Tasa o Cuota   (teclado + _hinput safety-net, valor del Excel)
        Luego clic en botón azul "Agregar" y verifica que apareció la fila.
        Máximo 2 intentos.
        """
        # CSS selector del botón azul "Agregar" impuesto — clase 'secondary'
        # es estable aunque el j_idt cambie tras cada AJAX re-render del fieldset.
        _BTN_CSS = r"#formNuevaFactura\:accordionConceptos\:filedSetImpuestos button.secondary"

        _UI_MAP = {
            "LOCAL": "LOCAL", "FEDERAL": "FEDERAL",
            "TRASLADO": "TRASLADO", "RETENCION": "RETENCION",
            "RETENCIÓN": "RETENCION", "TASA": "TASA",
            "CUOTA": "CUOTA", "EXENTO": "EXENTO",
        }

        def _ui(val: str) -> str:
            return _UI_MAP.get(str(val).strip().upper(), str(val).strip().upper())

        clave_impuesto     = imp.clave_impuesto.strip().upper()
        local_federal      = _ui(imp.local_federal)
        retencion_traslado = _ui(imp.retencion_traslado)
        tipo_factor        = _ui(imp.tipo_factor)

        if not clave_impuesto:
            raise ValueError("clave_impuesto vacío — revisar columna 'Tipo Impuesto' en Excel")
        if not local_federal:
            raise ValueError("local_federal vacío — revisar columna 'Local o Federal' en Excel")
        if not retencion_traslado:
            raise ValueError("retencion_traslado vacío — revisar columna 'Retencion o Traslado' en Excel")
        if not tipo_factor:
            raise ValueError("tipo_factor vacío — revisar columna 'Tipo Factor' en Excel")

        _MAX_ATTEMPTS = 2

        # IDs de los 5 campos del sub-form de impuesto (JSF 'process' scope).
        # Al pasarlos EXPLÍCITAMENTE a PrimeFaces.ab(), el servidor solo valida
        # estos componentes — selectOneCfdiTipoRelacionPago queda fuera → sin error.
        _IMPUESTO_PROCESS = (
            f"{_SEL_IMPUESTO} {_SEL_TIPO_FACTOR} "
            f"{_SEL_LOCAL_FED} {_SEL_TRASLADO_RET} "
            f"{_INPUT_TASA.replace('_input', '')}"
        )

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            if attempt > 1:
                log.warning("[_add_impuesto] Reintento %d/%d", attempt, _MAX_ATTEMPTS)

            # Garantizar que el módulo de impuestos esté abierto antes de cada
            # intento — el AJAX del impuesto anterior puede haberse re-renderizado
            # y colapsado el fieldset.
            self.expandir_impuestos()

            wait_for_ajax(self.driver)
            rows_before = self._count_impuesto_rows()
            log.info("[_add_impuesto] Filas antes: %d", rows_before)

            # ── 1. Impuesto (AJAX → cascada tipo_factor / local_fed / ret_tras) ──
            log.info("[INFO] Orden correcto de captura iniciado")
            log.info("[INFO] Impuesto → %s", clave_impuesto)
            self.force_jquery(_SEL_IMPUESTO + "_input", clave_impuesto)
            wait_for_ajax(self.driver)

            # ── 2. Tipo Factor (AJAX) ─────────────────────────────────────────
            log.info("[INFO] Tipo Factor → %s", tipo_factor)
            self.force_jquery(_SEL_TIPO_FACTOR + "_input", tipo_factor)
            wait_for_ajax(self.driver)

            # ── 3. Local o Federal (DOM directo — sin partial submit) ─────────
            # _jquery_set_select_by_label fija sel.value por JS sin disparar el
            # partial submit de PrimeFaces, evitando validar TipoRelacion.
            log.info("[INFO] Local/Federal → %s", local_federal)
            if not self._jquery_set_select_by_label(_SEL_LOCAL_FED + "_input", local_federal):
                log.warning("[_add_impuesto] local_fed DOM set falló para '%s'", local_federal)

            # ── 4. Retención o Traslado (DOM directo) ─────────────────────────
            log.info("[INFO] Retención/Traslado → %s", retencion_traslado)
            if not self._jquery_set_select_by_label(_SEL_TRASLADO_RET + "_input", retencion_traslado):
                log.warning("[_add_impuesto] ret_tras DOM set falló para '%s'", retencion_traslado)

            # ── 5. Tasa o Cuota (del Excel, una sola vez por intento) ─────────
            tasa_str = str(imp.tasa_cuota)
            log.info("[INFO] Tasa → %s", tasa_str)
            try:
                tasa_el = wait_for_element_clickable(self.driver, By.ID, _INPUT_TASA, timeout=8)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", tasa_el
                )
                tasa_el.click()
                tasa_el.send_keys(Keys.CONTROL, "a")
                tasa_el.send_keys(Keys.DELETE)
                tasa_el.send_keys(tasa_str)
                self.driver.execute_script("arguments[0].blur();", tasa_el)
                time.sleep(0.15)
            except Exception as _e:
                log.warning("[_add_impuesto] Tasa input falló (%s) — usando JS fallback", _e)
            # Safety-net: forzar _hinput directamente
            self.driver.execute_script(
                "var hid = document.getElementById(arguments[0].replace('_input','_hinput'));"
                "if (hid) hid.value = arguments[1];"
                "var inp = document.getElementById(arguments[0]);"
                "if (inp) {"
                "  inp.value = arguments[1];"
                "  try { inp.dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}"
                "}",
                _INPUT_TASA, tasa_str,
            )

            # ── DOM check antes de click ──────────────────────────────────────
            dom_state = {
                "clave":       self._read_select_value_text(_SEL_IMPUESTO     + "_input"),
                "tipo_factor": self._read_select_value_text(_SEL_TIPO_FACTOR  + "_input"),
                "local_fed":   self._read_select_value_text(_SEL_LOCAL_FED    + "_input"),
                "ret_tras":    self._read_select_value_text(_SEL_TRASLADO_RET + "_input"),
            }
            log.debug("[_add_impuesto] Estado DOM antes de Agregar: %s", dom_state)
            placeholders = {k for k, v in dom_state.items()
                            if v.lower() in ("", "local o federal", "retención o traslado",
                                             "retencion o traslado", "tipo factor", "?")}
            if placeholders:
                log.warning("[_add_impuesto] Campos vacíos antes de Agregar: %s", placeholders)

            # ── Click botón azul "Agregar" impuesto ───────────────────────────
            log.info("[INFO] Click botón azul Agregar impuesto")
            btn = None
            btn_id = None
            # Estrategia 1: clase 'secondary' dentro del fieldset — estable aunque
            # el j_idt cambie tras AJAX re-render.
            try:
                btn = wait_for_element_visible(
                    self.driver, By.CSS_SELECTOR, _BTN_CSS, timeout=10
                )
                btn_id = btn.get_attribute("id")
                log.debug("[_add_impuesto] btn encontrado por CSS class: %s", btn_id)
            except Exception:
                # Estrategia 2: XPath por texto dentro del fieldset (fallback)
                log.warning("[_add_impuesto] CSS class no encontrado — fallback XPath texto")
                try:
                    btn = wait_for_element_visible(
                        self.driver,
                        By.XPATH,
                        "(//button[.//span[normalize-space(.)='Agregar'] or "
                        "normalize-space(.)='Agregar']"
                        "[ancestor::*[contains(@id,'filedSetImpuestos')]])[last()]",
                        timeout=10,
                    )
                    btn_id = btn.get_attribute("id")
                    log.debug("[_add_impuesto] btn encontrado por XPath texto: %s", btn_id)
                except Exception:
                    # Estrategia 3: cualquier button no-tabla en el fieldset
                    log.warning("[_add_impuesto] XPath texto falló — fallback button no-tabla")
                    btn = wait_for_element_visible(
                        self.driver,
                        By.XPATH,
                        "//fieldset[contains(@id,'filedSetImpuestos')]"
                        "//div[not(ancestor::table)]//button",
                        timeout=10,
                    )
                    btn_id = btn.get_attribute("id")
                    log.debug("[_add_impuesto] btn encontrado por XPath no-tabla: %s", btn_id)

            self.scroll_to(btn)
            time.sleep(0.1)

            # PrimeFaces.ab() con 'p' explícito = solo los 5 campos del impuesto.
            # selectOneCfdiTipoRelacionPago NO está en la lista → JSF no lo valida.
            log.debug("[_add_impuesto] btn_id=%s | p=%s", btn_id, _IMPUESTO_PROCESS)
            pf_ok = self.driver.execute_script(
                "try {"
                "  PrimeFaces.ab({"
                "    s: arguments[0],"
                "    u: 'formNuevaFactura:accordionConceptos:filedSetImpuestos',"
                "    p: arguments[0] + ' ' + arguments[1]"
                "  });"
                "  return true;"
                "} catch(e) { return false; }",
                btn_id,
                _IMPUESTO_PROCESS,
            )
            if not pf_ok:
                log.warning("[_add_impuesto] PrimeFaces.ab falló — usando click directo")
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)

            wait_for_ajax(self.driver)
            time.sleep(0.3)

            # ── Capturar mensajes de error del servidor ───────────────────────
            server_msg = self.driver.execute_script(
                "var sels=['.ui-growl-message .ui-growl-message-summary',"
                "'.ui-growl-message .ui-growl-message-detail',"
                "'.ui-messages-error-summary','.ui-message-error-summary',"
                "'.ui-message-error-detail'];"
                "var msgs=[];"
                "for(var s=0;s<sels.length;s++){"
                "  var els=document.querySelectorAll(sels[s]);"
                "  for(var e=0;e<els.length;e++){"
                "    var t=(els[e].textContent||'').trim();"
                "    if(t) msgs.push(t);"
                "  }"
                "}"
                "return msgs.length?msgs.join(' | '):null;"
            )
            if server_msg:
                log.warning("[_add_impuesto] Mensaje del servidor: %s", server_msg)

            # ── Verificar fila ────────────────────────────────────────────────
            rows_after = self._count_impuesto_rows()
            log.info("[_add_impuesto] Filas después: %d (antes: %d)", rows_after, rows_before)

            if rows_after > rows_before:
                log.info("[INFO] Fila agregada correctamente (%d → %d filas)", rows_before, rows_after)
                return

            log.warning(
                "[_add_impuesto] Fila NO apareció (intento %d/%d). DOM: %s",
                attempt, _MAX_ATTEMPTS, dom_state,
            )
            time.sleep(0.5)

        raise RuntimeError(
            f"[_add_impuesto] No se pudo agregar impuesto '{clave_impuesto}' "
            f"después de {_MAX_ATTEMPTS} intentos. "
            "Verifica los valores del Excel y los IDs del formulario."
        )

    def add_all_conceptos(self, conceptos: List[ConceptoRow], impuestos: List[ImpuestoRow]):
        for c in conceptos:
            related_imps = [i for i in impuestos if i.id_concepto == c.id_concepto]
            self.add_concepto(c, related_imps)
     

    # ── Timbrar ─────────────────────────────────────────────────────────────

    def click_facturar(self, timeout: int = 60) -> Optional[str]:
        """Click the Facturar/Timbrar button. Returns UUID on success, raises on failure."""
        log.info("Clicking Facturar button (timeout=%ds)", timeout)

        # Wait for the button panel to appear (it's dynamic)
        wait_for_element_present(self.driver, By.ID, _PANEL_BOTONES, timeout=60)

        # Try known ID first, then CSS fallback
        btn = None
        try:
            btn = wait_for_element_clickable(self.driver, By.ID, _BTN_FACTURAR, timeout=15)
        except Exception:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, _BTN_FACTURAR_CSS)
            except Exception:
                # Fallback: any button in the panel
                panel = self.driver.find_element(By.ID, _PANEL_BOTONES)
                buttons = panel.find_elements(By.TAG_NAME, "button")
                if buttons:
                    btn = buttons[0]

        if not btn:
            raise RuntimeError("Facturar button not found in panel")

        self.scroll_to(btn)
        btn.click()
        log.info("Facturar clicked — waiting for timbrado response...")

        # Brief pause to let the app process the click and dismiss any
        # pre-existing transient messages before we start polling.
        import time as _t
        wait_for_ajax(self.driver)
        _t.sleep(2.0)

        # Wait up to `timeout` s for success button OR error toast
        return self._wait_for_timbrado_result(timeout)

    def _wait_for_timbrado_result(self, timeout: int) -> Optional[str]:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        descarga_locator = (By.CSS_SELECTOR, _BTN_DESCARGA_CSS)
        toast_locator    = (By.CSS_SELECTOR,
            ".ui-growl-message-error, .ui-growl-message-fatal, .ui-growl-message-warn,"
            " div.ui-messages-error, .ui-message-error")

        def _result_appeared(driver):
            return (is_element_present(driver, *descarga_locator) or
                    is_element_present(driver, *toast_locator))

        try:
            WebDriverWait(self.driver, timeout).until(_result_appeared)
        except Exception:
            raise TimeoutError(f"No timbrado result after {timeout}s")

        # Check success
        if is_element_present(self.driver, *descarga_locator):
            uuid = self._extract_uuid()
            log.info("Timbrado exitoso! UUID=%s", uuid)
            return uuid

        # Error path — only raise if the toast has actual text to avoid
        # false positives from transient / empty DOM elements.
        try:
            toast_el = self.driver.find_element(*toast_locator)
            msg = toast_el.text.strip()
        except Exception:
            msg = ""

        if not msg:
            # Empty toast — could be a stale element; keep waiting
            from selenium.webdriver.support.ui import WebDriverWait
            try:
                WebDriverWait(self.driver, timeout).until(
                    lambda d: is_element_present(d, *descarga_locator)
                )
                uuid = self._extract_uuid()
                log.info("Timbrado exitoso (segunda espera)! UUID=%s", uuid)
                return uuid
            except Exception:
                raise TimeoutError(f"No timbrado result after {timeout}s")

        log.error("Timbrado failed: %s", msg)
        raise RuntimeError(f"TIMBRADO_ERROR: {msg}")

    def _extract_uuid(self) -> str:
        """Try to extract the UUID from the page after successful timbrado."""
        # Common locations: panel with UUID text, input field, or download URL
        candidates = [
            "//span[contains(text(),'UUID') or contains(text(),'Folio Fiscal')]/../following-sibling::*",
            "//*[contains(@id,'uuid') or contains(@id,'UUID')]",
            "//*[contains(@id,'folioFiscal')]",
        ]
        for xpath in candidates:
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                text = el.text.strip() or el.get_attribute("value") or ""
                if len(text) == 36 and text.count("-") == 4:
                    return text
            except Exception:
                continue
        # Fallback — return empty string; can be captured from ZIP filename later
        log.warning("UUID not found on page, will extract from downloaded ZIP")
        return ""

    # ── Download ─────────────────────────────────────────────────────────────

    def click_descarga(self, downloads_dir: str, timeout: int = 60) -> tuple:
        """Click 'Descarga CFDI', wait for ZIP, and return (zip_path, uuid_from_filename).

        Handles Chrome's 'Sin confirmar' partial-download files by ignoring
        pre-existing .crdownload entries and waiting for new ones to complete.
        """
        import glob, time as _time, re as _re

        # Snapshot state BEFORE clicking to detect newly created files
        pre_zips = set(glob.glob(os.path.join(downloads_dir, "*.zip")))
        pre_crdownloads = set(glob.glob(os.path.join(downloads_dir, "*.crdownload")))
        log.info(
            "Pre-click state — ZIPs: %d  .crdownload: %d",
            len(pre_zips), len(pre_crdownloads),
        )

        log.info("Clicking Descarga CFDI")
        try:
            btn = wait_for_element_clickable(self.driver, By.ID, _BTN_DESCARGA, timeout=10)
        except Exception:
            btn = wait_for_element_clickable(self.driver, By.CSS_SELECTOR, _BTN_DESCARGA_CSS, timeout=10)

        self.scroll_to(btn)
        btn.click()

        uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        deadline = _time.time() + timeout

        while _time.time() < deadline:
            # New .crdownload files (download in progress — not yet complete)
            new_crdownloads = [
                c for c in glob.glob(os.path.join(downloads_dir, "*.crdownload"))
                if c not in pre_crdownloads
            ]
            if new_crdownloads:
                log.debug("Download in progress: %s", new_crdownloads)
                _time.sleep(1)
                continue

            # New ZIP files (download complete)
            new_zips = [
                z for z in glob.glob(os.path.join(downloads_dir, "*.zip"))
                if z not in pre_zips
            ]
            if new_zips:
                newest = max(new_zips, key=os.path.getmtime)
                log.info("Downloaded ZIP: %s", newest)
                basename = os.path.basename(newest)
                match = _re.search(uuid_pattern, basename)
                uuid_from_zip = match.group().lower() if match else ""
                return newest, uuid_from_zip

            _time.sleep(1)

        raise TimeoutError(f"Download ZIP not found in {downloads_dir} after {timeout}s")

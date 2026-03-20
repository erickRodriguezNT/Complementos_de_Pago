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


class FacturaPage(BasePage):

    def navigate(self, url: str):
        log.info("Navigating to factura form: %s", url)
        self.driver.get(url)
        wait_for_ajax(self.driver)

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

        # Centro de Consumo
        self.select_one_menu_exact(_CC_SELECT, cc)

    # ── Receptor ────────────────────────────────────────────────────────────

    def fill_receptor(self, rfc: str, nombre: str, uso_cfdi: str, regimen: str,
                      domicilio_cp: str, email: str):
        log.info("Filling Receptor: rfc=%s", rfc)

        # 1. Type RFC and press TAB — this fires onblur which triggers the
        #    PrimeFaces AJAX that auto-populates:
        #      • Nombre/Razón Social
        #      • Uso de CFDI
        #      • Régimen Fiscal del Receptor
        #      • Domicilio Fiscal (C.P.)
        rfc_el = wait_for_element_clickable(self.driver, By.ID, _RFC_RECEPTOR)
        rfc_el.clear()
        rfc_el.send_keys(rfc)
        rfc_el.send_keys(Keys.TAB)   # triggers onblur → AJAX auto-fill
        log.info("TAB pressed — waiting for receptor fields autofill via AJAX")

        # 2. Wait for PrimeFaces spinner to disappear
        wait_for_ajax(self.driver)

        # 3. Wait explicitly until Uso de CFDI is auto-populated (confirming
        #    that the AJAX response has been applied to the DOM).
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: d.find_element(By.ID, _USO_CFDI + "_label")
                           .get_attribute("textContent").strip()
                not in ("", "Uso de CFDI *")
            )
            log.info("Receptor fields auto-filled by AJAX")
        except Exception:
            log.warning("Uso CFDI label did not populate within 15 s — continuing anyway")

        # 4. All main fields (nombre, uso_cfdi, regimen, domicilio) are now
        #    auto-filled from the stored receptor profile. Do NOT re-open the
        #    dropdowns, as that would trigger further AJAX calls unnecessarily.
        log.debug("nombre/uso_cfdi/regimen/domicilio auto-filled — skipping manual override")

        # 5. Only fill Email, which is NOT part of the auto-fill response.
        try:
            email_input = self.driver.find_element(By.ID, _EMAIL_RECEPTOR + "_input")
            email_input.clear()
            email_input.send_keys(email)
        except Exception:
            log.warning("Email field not found, skipping")

    # ── Comprobante ─────────────────────────────────────────────────────────

    def _select_tipo_comprobante(self, tipo: str):
        """Select Tipo de Comprobante using the _label element as trigger."""
        widget_id = _TIPO_COMPROBANTE
        label_id  = _TIPO_COMPROBANTE_LABEL
        panel_id  = widget_id + "_panel"
        target    = tipo.strip().lower()

        for attempt in range(3):
            try:
                trigger = wait_for_element_present(self.driver, By.ID, widget_id)

                # Buscar el botón trigger interno (la flechita)
                trigger_btn = trigger.find_element(By.CSS_SELECTOR, ".ui-selectonemenu-trigger")

                self.scroll_to(trigger_btn)

                try:
                    trigger_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", trigger_btn)
                self.scroll_to(trigger)

                try:
                    trigger.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", trigger)

                wait_for_ajax(self.driver)

                try:
                    panel = wait_for_element_visible(self.driver, By.ID, panel_id, timeout=5)
                except:
                    log.warning("Panel clásico no apareció, buscando overlay alternativo...")

                    panels = self.driver.find_elements(By.CSS_SELECTOR, "div.ui-selectonemenu-panel")
                    visible_panels = [p for p in panels if p.is_displayed()]

                    if not visible_panels:
                        raise RuntimeError("No se encontró ningún panel visible para Tipo de Comprobante")

                    panel = visible_panels[-1]

                # AQUÍ ESTABA EL ERROR
                items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")

                if not items:
                    raise ValueError(
                        f"_select_tipo_comprobante: panel '{panel_id}' has no items"
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
                                f"Tipo comprobante: clicked '{texto}' but "
                                f"_label shows '{valor_final}' (expected '{tipo}')"
                            )

                        log.info("Tipo comprobante seleccionado: '%s'", valor_final)
                        return

                opciones = [i.text.strip() for i in items if i.text.strip()]
                raise ValueError(
                    f"_select_tipo_comprobante: '{tipo}' not found. Available: {opciones}"
                )

            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                log.warning(
                    "StaleElement in _select_tipo_comprobante (attempt %d/3) — retrying…",
                    attempt + 1
                )
                wait_for_ajax(self.driver)


    def fill_comprobante(self, tipo: str, serie: str, forma_pago: str,
                         metodo_pago: str, moneda: str):
        log.info("Filling Comprobante: tipo=%s serie=%s forma=%s", tipo, serie, forma_pago)
        self._select_tipo_comprobante(tipo)
        self.select_one_menu_contains(_SERIE, serie)
        self.select_one_menu_contains(_FORMA_PAGO, forma_pago)
        self.select_one_menu_contains(_METODO_PAGO, metodo_pago)
        self.fill_moneda(moneda)

    def fill_moneda(self, moneda: str):
        """Fill Moneda autocomplete in a more tolerant way.

        This field appears to accept keyboard confirmation better than waiting
        for the generic autocomplete panel.
        """
        log.info("Filling Moneda: %s", moneda)

        campo = wait_for_element_clickable(self.driver, By.ID, _MONEDA_AC, timeout=10)
        self.scroll_to(campo)

        try:
            campo.clear()
        except Exception:
            pass

        # Limpieza extra por si PrimeFaces conserva valor parcial
        campo.send_keys(Keys.CONTROL, "a")
        campo.send_keys(Keys.BACKSPACE)

        campo.send_keys(moneda)
        time.sleep(0.6)  # esperar sugerencias del autocomplete

        # Confirmar por teclado en vez de depender siempre del panel visual
        campo.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.2)
        campo.send_keys(Keys.ENTER)
        time.sleep(0.3)
        campo.send_keys(Keys.TAB)

        wait_for_ajax(self.driver)

        valor_final = (campo.get_attribute("value") or "").strip()
        log.info("Moneda final capturada en input: '%s'", valor_final)

        if moneda.upper() not in valor_final.upper():
            log.warning("Moneda '%s' no quedó confirmada exactamente, valor actual: '%s'", moneda, valor_final)


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
        time.sleep(0.2)
        # Empujar hacia abajo para que el legend '+' quede visible sobre el pliegue
        self.driver.execute_script("window.scrollBy(0, 150);")
        time.sleep(0.2)

        # 3. Localizar el botón '+' (legend > span del fieldset)
        log.info("[expandir_impuestos] Esperando botón '+' de Impuestos...")
        btn = wait_for_element_clickable(
            self.driver,
            By.CSS_SELECTOR,
            _BTN_EXPANDIR_IMPUESTOS_CSS,
            timeout=10,
        )

        # 4. Scroll al botón '+' y click (JS como fallback)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            btn,
        )
        time.sleep(0.2)
        log.info("[expandir_impuestos] Dando clic en el botón '+' para expandir...")
        try:
            btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn)

        wait_for_ajax(self.driver)
        time.sleep(0.8)

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
        time.sleep(1.5)  # dar tiempo al DOM para mostrar/ocultar el fieldset de impuestos

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
                time.sleep(0.4)

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
        log.info("[Paso 8] Dando clic en 'Agregar Concepto' (id=%d)...", concepto.id_concepto)
        self.safe_click(_BTN_AGREGAR_CONC)
        wait_for_ajax(self.driver)
        time.sleep(1.5)
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
        time.sleep(0.8)

        log.info("─── add_concepto FIN  id=%d", concepto.id_concepto)


 
    def _add_impuesto(self, imp: ImpuestoRow):
        """Llena el sub-formulario de un impuesto y hace clic en el botón azul 'Agregar'."""

        # ── Normalizar valores del Excel al texto exacto del UI ───────────────
        # El UI de FACTO muestra mayúsculas (FEDERAL, TRASLADO, TASA, etc.)
        _UI_MAP = {
            "LOCAL":     "LOCAL",
            "FEDERAL":   "FEDERAL",
            "TRASLADO":  "TRASLADO",
            "RETENCION": "RETENCION",
            "RETENCIÓN": "RETENCION",
            "TASA":      "TASA",
            "CUOTA":     "CUOTA",
            "EXENTO":    "EXENTO",
        }

        def _ui(val: str) -> str:
            return _UI_MAP.get(str(val).strip().upper(), str(val).strip().upper())

        clave_impuesto     = imp.clave_impuesto.strip().upper()        # IVA / ISR / IEPS
        local_federal      = _ui(imp.local_federal)                    # LOCAL / FEDERAL
        retencion_traslado = _ui(imp.retencion_traslado)               # TRASLADO / RETENCION
        tipo_factor        = _ui(imp.tipo_factor)                      # TASA / CUOTA / EXENTO

        # Validaciones
        if not clave_impuesto:
            raise ValueError("clave_impuesto vacío — revisar columna 'Tipo Impuesto' en Excel")
        if not local_federal:
            raise ValueError("local_federal vacío — revisar columna 'Local o Federal' en Excel")
        if not retencion_traslado:
            raise ValueError("retencion_traslado vacío — revisar columna 'Retencion o Traslado' en Excel")
        if not tipo_factor:
            raise ValueError("tipo_factor vacío — revisar columna 'Tipo Factor' en Excel")

        log.info(
            "[_add_impuesto] clave=%s | local_fed=%s | ret_tras=%s | factor=%s | tasa=%s",
            clave_impuesto, local_federal, retencion_traslado, tipo_factor, imp.tasa_cuota,
        )

        wait_for_ajax(self.driver)

        # 1. Clave impuesto (ej. 002 IVA) — búsqueda parcial
        log.info("[_add_impuesto] Paso 1 — Clave impuesto: %s", clave_impuesto)
        self.select_one_menu_contains(_SEL_IMPUESTO, clave_impuesto)
        wait_for_ajax(self.driver)
        time.sleep(0.3)

        # 2. Tipo Factor
        log.info("[_add_impuesto] Paso 2 — Tipo Factor: %s", tipo_factor)
        self.select_one_menu_contains(_SEL_TIPO_FACTOR, tipo_factor)
        wait_for_ajax(self.driver)
        time.sleep(0.3)

        # 2️⃣ LOCAL / FEDERAL  ← AQUÍ VA TU LÍNEA
        self.select_one_menu_exact(_SEL_LOCAL_FED, local_federal)
        wait_for_ajax(self.driver)
        time.sleep(1)

        # 3️⃣ RETENCIÓN / TRASLADO  ← AQUÍ VA TU LÍNEA
        self.select_one_menu_exact(_SEL_TRASLADO_RET, retencion_traslado)
        wait_for_ajax(self.driver)
        time.sleep(1)

        # 5. Tasa o Cuota
        log.info("[_add_impuesto] Paso 5 — Tasa/Cuota: %s", imp.tasa_cuota)
        self._clear_and_type(_INPUT_TASA, str(imp.tasa_cuota))
        time.sleep(0.2)

        # 6. Clic en el botón azul 'Agregar' del sub-formulario de impuestos
        log.info("[_add_impuesto] Paso 6 — Clic en botón azul 'Agregar' impuesto...")
        btn_agregar = wait_for_element_clickable(self.driver, By.ID, _BTN_AGREGAR_IMP, timeout=10)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            btn_agregar,
        )
        time.sleep(0.2)
        try:
            btn_agregar.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", btn_agregar)

        wait_for_ajax(self.driver)
        time.sleep(0.5)
        log.info("[_add_impuesto] Impuesto agregado correctamente.")

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

        # Wait up to `timeout` s for success button OR error toast
        return self._wait_for_timbrado_result(timeout)

    def _wait_for_timbrado_result(self, timeout: int) -> Optional[str]:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        descarga_locator = (By.CSS_SELECTOR, _BTN_DESCARGA_CSS)
        toast_locator    = (By.CSS_SELECTOR, "div.ui-growl-message, div.ui-messages-error, .ui-message-error")

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

        # Error path
        toast_el = self.driver.find_element(*toast_locator)
        msg = toast_el.text.strip()
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

    def click_descarga(self, downloads_dir: str, timeout: int = 30) -> str:
        """Click 'Descarga CFDI' and return path to downloaded ZIP."""
        log.info("Clicking Descarga CFDI")
        try:
            btn = wait_for_element_clickable(self.driver, By.ID, _BTN_DESCARGA, timeout=10)
        except Exception:
            btn = wait_for_element_clickable(self.driver, By.CSS_SELECTOR, _BTN_DESCARGA_CSS, timeout=10)

        self.scroll_to(btn)
        btn.click()

        # Wait for file to appear in downloads dir
        import glob, time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            zips = glob.glob(os.path.join(downloads_dir, "*.zip"))
            if zips:
                newest = max(zips, key=os.path.getmtime)
                log.info("Downloaded ZIP: %s", newest)
                return newest
            _time.sleep(1)

        raise TimeoutError(f"Download ZIP not found in {downloads_dir} after {timeout}s")

"""Complemento de Pago Page Object.

Reuses the same factura_manual_40.xhtml page.
Flow: change Tipo to PAGO → fill pago header → add DR panel → Timbrar.

NOTE: DR panel field IDs are PLACEHOLDERS — fill in after live inspection.
"""
from typing import Optional
from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from pages.factura_page import (
    FacturaPage,
    _EMISOR_SELECT, _EMISOR_FILTER, _SUCURSAL_SELECT, _CC_SELECT,
    _RFC_RECEPTOR, _USO_CFDI, _REGIMEN_RECEPTOR, _DOMICILIO_RECEPTOR,
    _TIPO_COMPROBANTE, _FORMA_PAGO, _METODO_PAGO, _MONEDA_AC,
    _PANEL_BOTONES, _BTN_FACTURAR, _BTN_FACTURAR_CSS,
)
from utils.waits import (
    wait_for_ajax, wait_for_element_clickable,
    wait_for_element_visible, wait_for_element_present,
    is_element_present,
)
from utils.logger import get_logger

log = get_logger("complemento_pago_page")

# ═══════════════════════════════════════════════════════════════════════════════
# DR PANEL LOCATORS  — TODO: verify all IDs with live browser inspection
# ═══════════════════════════════════════════════════════════════════════════════
_BTN_AGREGAR_DR     = "formNuevaFactura:accordionDatosComprobante:buttonAgregarDocRelacionado"  # TODO
_DR_PANEL           = "formNuevaFactura:accordionDatosComprobante:panelDocRelacionado"           # TODO

_DR_UUID_INPUT      = "formNuevaFactura:accordionDatosComprobante:inputUUIDRelacionado"          # TODO
_DR_PARCIALIDAD     = "formNuevaFactura:accordionDatosComprobante:inputNumeroParcialidad"        # TODO
_DR_MONTO           = "formNuevaFactura:accordionDatosComprobante:inputMontoPagado_input"        # TODO
_DR_SALDO_ANT       = "formNuevaFactura:accordionDatosComprobante:inputImporteSaldoAnterior_input"  # TODO
_DR_SALDO_INS       = "formNuevaFactura:accordionDatosComprobante:inputImporteSaldoInsoluto_input"  # TODO
_DR_MONEDA          = "formNuevaFactura:accordionDatosComprobante:selectOneDRMoneda"             # TODO
_BTN_GUARDAR_DR     = "formNuevaFactura:accordionDatosComprobante:buttonGuardarDocRelacionado"   # TODO

# Pago header (within PAGO type comprobante)
_FORMA_PAGO_COMP    = "formNuevaFactura:accordionDatosComprobante:selectOneFormaPagoComplemento"  # TODO
_MONEDA_COMP_AC     = "formNuevaFactura:accordionDatosComprobante:autoCompleteMonedaComplemento_input"  # TODO

# CSS fallbacks
_BTN_AGREGAR_DR_CSS = "button[id*='AgregarDoc'], button[id*='agregarDoc'], button[id*='DR']"
_BTN_GUARDAR_DR_CSS = "button[id*='GuardarDoc'], button[id*='guardarDoc']"
_DR_UUID_CSS        = "input[id*='UUID'], input[id*='uuid']"
_DR_PARCIALIDAD_CSS = "input[id*='arcialidad'], input[id*='umero']"
_DR_MONTO_CSS       = "input[id*='onto'], input[id*='onto']"

# Download locators (shared with factura_page)
from pages.factura_page import _BTN_DESCARGA, _BTN_DESCARGA_CSS


class ComplementoPagoPage(FacturaPage):
    """Extends FacturaPage with Complemento de Pago-specific steps."""

    def fill_emisor_receptor_for_pago(self, rfc_emisor: str, sucursal: str, cc: str,
                                       rfc_receptor: str, uso_cfdi: str,
                                       regimen: str, domicilio_cp: str, email: str):
        """Fill header data for a new Complemento de Pago (same page, new timbrado)."""
        self.fill_emisor(rfc_emisor, sucursal, cc)
        self.fill_receptor(rfc_receptor, "PUBLICO EN GENERAL", uso_cfdi, regimen, domicilio_cp, email)

    def set_tipo_pago(self):
        """Change Tipo Comprobante to PAGO."""
        log.info("Setting Tipo Comprobante = PAGO")
        self.select_one_menu_contains(_TIPO_COMPROBANTE, "PAGO")

    def fill_pago_header(self, forma_pago: str = "01", moneda: str = "MXN"):
        """Fill the Forma de Pago and Moneda for the complemento header."""
        log.info("Filling pago header: forma=%s moneda=%s", forma_pago, moneda)
        try:
            self.select_one_menu_contains(_FORMA_PAGO_COMP, forma_pago)
        except Exception:
            # Fallback to same field as factura if panel doesn't split
            self.select_one_menu_contains(_FORMA_PAGO, forma_pago)
        try:
            self.autocomplete(_MONEDA_COMP_AC, moneda, moneda)
        except Exception:
            self.autocomplete(_MONEDA_AC, moneda, moneda)

    def add_documento_relacionado(self, uuid_factura: str, num_parcialidad: int,
                                  monto_pago: float, saldo_anterior: float,
                                  saldo_insoluto: float, moneda_dr: str = "MXN"):
        """Open the DR panel, fill all fields, and save."""
        log.info("Adding DR: uuid=%s parcialidad=%d monto=%.2f saldo_ant=%.2f saldo_ins=%.2f",
                 uuid_factura, num_parcialidad, monto_pago, saldo_anterior, saldo_insoluto)

        # Click "Agregar Documento Relacionado DR" button
        try:
            self.safe_click(_BTN_AGREGAR_DR)
        except Exception:
            self.safe_click_css(_BTN_AGREGAR_DR_CSS)

        # Wait for DR panel
        try:
            wait_for_element_visible(self.driver, By.ID, _DR_PANEL, timeout=15)
        except Exception:
            log.warning("DR panel ID not found, proceeding without explicit wait")

        # UUID
        self._fill_dr_field(_DR_UUID_INPUT, _DR_UUID_CSS, uuid_factura)

        # Número de Parcialidad
        self._fill_dr_field(_DR_PARCIALIDAD, _DR_PARCIALIDAD_CSS, str(num_parcialidad))

        # Moneda DR
        try:
            self.select_one_menu_contains(_DR_MONEDA, moneda_dr)
        except Exception:
            log.warning("DR Moneda field not found, skipping")

        # Monto Pagado
        self._fill_dr_field(_DR_MONTO, _DR_MONTO_CSS, f"{monto_pago:.2f}")

        # Saldo Anterior
        self._fill_dr_field(_DR_SALDO_ANT, None, f"{saldo_anterior:.2f}")

        # Saldo Insoluto
        self._fill_dr_field(_DR_SALDO_INS, None, f"{saldo_insoluto:.2f}")

        # Save / Guardar DR
        try:
            self.safe_click(_BTN_GUARDAR_DR)
        except Exception:
            self.safe_click_css(_BTN_GUARDAR_DR_CSS)

        wait_for_ajax(self.driver)
        log.info("DR saved successfully")

    def _fill_dr_field(self, field_id: str, css_fallback: Optional[str], value: str):
        """Fill a DR panel field, using CSS fallback if ID fails."""
        try:
            el = wait_for_element_clickable(self.driver, By.ID, field_id, timeout=10)
            el.clear()
            el.send_keys(value)
        except Exception:
            if css_fallback:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, css_fallback)
                    el.clear()
                    el.send_keys(value)
                except Exception:
                    log.warning("DR field '%s' (css: %s) not found, skipping", field_id, css_fallback)
            else:
                log.warning("DR field '%s' not found, skipping", field_id)

    def timbrar_complemento(self, timeout: int = 60) -> str:
        """Click Facturar and return UUID. Wraps FacturaPage.click_facturar."""
        return self.click_facturar(timeout=timeout)

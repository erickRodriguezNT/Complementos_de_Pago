"""Base Page Object with PrimeFaces interaction helpers."""
import time
import unicodedata
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException

from utils.waits import (
    wait_for_ajax, wait_for_element_clickable,
    wait_for_element_visible, wait_for_element_present,
    is_element_present,
)
from utils.logger import get_logger

log = get_logger("base_page")


def _norm(s: str) -> str:
    """Lowercase + strip accents for accent-insensitive comparisons."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    )


class BasePage:
    def __init__(self, driver):
        self.driver = driver

    # ── Low-level helpers ──────────────────────────────────────────────────

    def _find(self, element_id: str):
        return self.driver.find_element(By.ID, element_id)

    def _find_css(self, css: str):
        return self.driver.find_element(By.CSS_SELECTOR, css)

    def _find_xpath(self, xpath: str):
        return self.driver.find_element(By.XPATH, xpath)

    def _clear_and_type(self, element_id: str, value: str):
        el = wait_for_element_clickable(self.driver, By.ID, element_id)
        el.clear()
        el.send_keys(value)

    # ── PrimeFaces SelectOneMenu ───────────────────────────────────────────
    # PrimeFaces renders: hidden <select> + visible <div id=widget_id> trigger.
    # The outer div (widget_id) is the reliable click target in PrimeFaces 6.x.
    # The _label child shows the currently selected value after selection.

    def select_one_menu_contains(self, widget_id: str, partial_label: str):
        """Select first option whose label CONTAINS partial_label (case-insensitive).

        Uses the outer widget div (widget_id) as trigger — same approach that
        worked originally.  Validates the selection by reading the refreshed
        _label element (never reads the stale item reference after AJAX).
        Retries up to 3× on StaleElementReferenceException.
        """
        panel_id = widget_id + "_panel"
        label_id = widget_id + "_label"
        target   = _norm(partial_label.strip())

        for attempt in range(3):
            try:
                # 1. Click the outer SelectOneMenu container div.
                #    This is more reliable than _label in PrimeFaces 6.x because
                #    the widget div includes the arrow-trigger hit area.
                trigger = wait_for_element_clickable(self.driver, By.ID, widget_id)
                self.scroll_to(trigger)
                try:
                    trigger.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", trigger)

                wait_for_ajax(self.driver)

                # 2. Wait for the floating panel and enumerate items
                panel = wait_for_element_visible(self.driver, By.ID, panel_id)
                items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")

                if not items:
                    raise ValueError(
                        f"SelectOneMenu '{widget_id}' panel opened but contains no items"
                    )

                # 3. Case-insensitive partial match.
                #    Capture item text BEFORE clicking — reading it afterwards
                #    returns '' because the element is stale after AJAX refresh.
                for item in items:
                    texto = item.text.strip()
                    if target in _norm(texto):
                        self.scroll_to(item)
                        try:
                            item.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", item)
                        wait_for_ajax(self.driver)

                        # 4. Validate via the refreshed _label (not the stale item ref)
                        try:
                            valor_final = self.driver.find_element(
                                By.ID, label_id
                            ).text.strip()
                        except Exception:
                            valor_final = texto  # fall back to pre-click capture

                        if not valor_final:
                            raise ValueError(
                                f"SelectOneMenu '{widget_id}': clicked '{texto}' but "
                                f"_label is empty after selection (expected '{partial_label}')"
                            )
                        if target not in _norm(valor_final):
                            raise ValueError(
                                f"SelectOneMenu '{widget_id}': clicked '{texto}' but "
                                f"_label shows '{valor_final}' (expected '{partial_label}')"
                            )

                        log.debug(
                            "SelectOneMenu '%s' → '%s'", widget_id, valor_final
                        )
                        return

                opciones = [i.text.strip() for i in items if i.text.strip()]
                raise ValueError(
                    f"No option containing '{partial_label}' in SelectOneMenu "
                    f"'{widget_id}'. Available: {opciones}"
                )

            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                log.warning(
                    "StaleElement in SelectOneMenu '%s' (attempt %d/3) — retrying…",
                    widget_id, attempt + 1
                )
                wait_for_ajax(self.driver)

    def select_one_menu_exact(self, widget_id: str, value: str):
        """Select option EXACT match (no contains)."""
        label_id = widget_id + "_label"
        panel_id = widget_id + "_panel"
        target = value.strip().lower()

        # Abrir dropdown
        trigger = wait_for_element_clickable(self.driver, By.ID, label_id)
        self.scroll_to(trigger)
        trigger.click()
        wait_for_ajax(self.driver)

        # Esperar panel
        panel = wait_for_element_visible(self.driver, By.ID, panel_id)

        items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")

        for item in items:
            texto = item.text.strip()

            # seleccion de CP 
            if texto.lower() == target:
                self.scroll_to(item)
                item.click()
                wait_for_ajax(self.driver)

                log.debug("SelectOneMenu EXACT '%s' → '%s'", widget_id, texto)
                return

        opciones = [i.text.strip() for i in items if i.text.strip()]
        raise ValueError(
            f"select_one_menu_exact: '{value}' not found. Available: {opciones}"
        )

    def select_one_menu_by_id_input(self, input_id: str, partial_label: str):
        """Convenience variant where the base widget_id ends in _input."""
        base_id = input_id.replace("_input", "")
        self.select_one_menu_contains(base_id, partial_label)

    # ── PrimeFaces AutoComplete ────────────────────────────────────────────

    def autocomplete(self, input_id: str, text: str, suggestion_text: str = None,
                     timeout: int = 15):
        """Type into a PrimeFaces AutoComplete and confirm selection.

        Strategy (keyboard-first — avoids relying on transient suggestion panels,
        which is what makes SAT-catalogue fields like Clave Unidad fail):

          A. Clear → type → brief AJAX wait.
          B. ARROW_DOWN + ENTER → read back field value.
             If the value contains the target: done (TAB to close).
          C. Fallback: scan the visible panel and click a matching item.
          D. Last resort: TAB out and log a warning (never hard-fail).
        """
        target = (suggestion_text or text).strip()

        el = wait_for_element_clickable(self.driver, By.ID, input_id)
        self.scroll_to(el)

        # Clear with triple strategy to handle PrimeFaces partial-value state
        el.clear()
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.BACKSPACE)
        time.sleep(0.2)

        el.send_keys(text)
        time.sleep(0.8)                   # let autocomplete AJAX query fire
        wait_for_ajax(self.driver, timeout=timeout)

        # ── A: keyboard confirmation ──────────────────────────────────────
        el.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.3)
        el.send_keys(Keys.ENTER)
        time.sleep(0.4)
        wait_for_ajax(self.driver)

        valor = (el.get_attribute("value") or "").strip()
        if target.lower() in valor.lower():
            log.debug(
                "AutoComplete '%s' confirmed via keyboard → '%s'", input_id, valor
            )
            el.send_keys(Keys.TAB)
            wait_for_ajax(self.driver)
            return

        # ── B: visual panel ───────────────────────────────────────────────
        log.debug(
            "AutoComplete '%s': keyboard got '%s', trying panel…", input_id, valor
        )
        try:
            panel = wait_for_element_visible(
                self.driver, By.CSS_SELECTOR,
                "ul.ui-autocomplete-items", timeout=timeout
            )
            items = panel.find_elements(By.CSS_SELECTOR, "li.ui-autocomplete-item")
            for item in items:
                if target.lower() in item.text.strip().lower():
                    item.click()
                    wait_for_ajax(self.driver)
                    log.debug(
                        "AutoComplete '%s' confirmed via panel → '%s'",
                        input_id, item.text.strip()
                    )
                    el.send_keys(Keys.TAB)
                    wait_for_ajax(self.driver)
                    return
            # Fallback: first visible item
            if items:
                first_text = items[0].text.strip()
                items[0].click()
                wait_for_ajax(self.driver)
                log.debug(
                    "AutoComplete '%s' → fallback first item '%s'", input_id, first_text
                )
                el.send_keys(Keys.TAB)
                wait_for_ajax(self.driver)
                return
        except Exception as panel_exc:
            log.warning(
                "AutoComplete '%s' panel approach failed: %s", input_id, panel_exc
            )

        # ── C: last resort — TAB out and warn ────────────────────────────
        log.warning(
            "AutoComplete '%s': could not confirm '%s' (current='%s') — TAB out",
            input_id, target, valor
        )
        el.send_keys(Keys.TAB)
        wait_for_ajax(self.driver)

    # ── Scroll & safe click ───────────────────────────────────────────────

    def scroll_to(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)

    def safe_click(self, element_id: str):
        el = wait_for_element_clickable(self.driver, By.ID, element_id)
        self.scroll_to(el)
        el.click()
        wait_for_ajax(self.driver)

    def safe_click_css(self, css: str):
        el = wait_for_element_clickable(self.driver, By.CSS_SELECTOR, css)
        self.scroll_to(el)
        el.click()
        wait_for_ajax(self.driver)

    # ── Screenshot ────────────────────────────────────────────────────────

    def take_screenshot(self, name: str, screenshots_dir: str):
        import os
        os.makedirs(screenshots_dir, exist_ok=True)
        ts = int(time.time())
        path = os.path.join(screenshots_dir, f"{name}_{ts}.png")
        self.driver.save_screenshot(path)
        log.info("Screenshot saved: %s", path)
        return path

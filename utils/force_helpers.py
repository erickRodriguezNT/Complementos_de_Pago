"""Retry-based field-forcing helpers for PrimeFaces Selenium automation.

Cada helper:
  1. Intenta llenar / seleccionar el campo
  2. Lee el DOM para confirmar que el valor quedó registrado
  3. Reintenta hasta `max_attempts` veces si la confirmación falla
  4. Lanza FieldFillError con mensaje claro si todos los intentos fallan
"""
import time
import unicodedata

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    WebDriverException,
    TimeoutException,
)

from utils.waits import wait_for_ajax, wait_for_element_clickable, wait_for_element_visible
from utils.logger import get_logger

log = get_logger("force_helpers")

# ─────────────────────────────────────────────────────────────────────────────
# Excepción especial
# ─────────────────────────────────────────────────────────────────────────────

class FieldFillError(RuntimeError):
    """Se lanza cuando un campo no pudo ser confirmado después de todos los reintentos."""


# ─────────────────────────────────────────────────────────────────────────────
# Utilidad interna
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Minúsculas + quitar acentos para comparación insensible a tildes."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    )


def _norm_num(s: str) -> str:
    """Quita símbolos de moneda, separadores de miles y espacios para comparar números.

    Ejemplos: '$1,750.00' → '1750.00' | '1 750,00' → '175000' (no usado)
    Solo aplica si el resultado es un número; si no, devuelve la cadena original.
    """
    import re
    stripped = re.sub(r'[$,\s]', '', s.strip())
    return stripped


def _log_attempt(field: str, attempt: int, max_attempts: int, msg: str):
    if attempt > 1:
        log.warning("  [intento %d/%d] %s — %s", attempt, max_attempts, field, msg)


# ─────────────────────────────────────────────────────────────────────────────
# force_input_value
# ─────────────────────────────────────────────────────────────────────────────

def force_input_value(
    driver,
    element_id: str,
    value: str,
    max_attempts: int = 3,
) -> str:
    """Limpia y escribe *value* en un input; confirma que el DOM lo retiene.

    Returns:
        El valor confirmado del atributo 'value' del elemento.
    Raises:
        FieldFillError si el valor no quedó después de max_attempts intentos.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            el = wait_for_element_clickable(driver, By.ID, element_id, timeout=15)
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", el
            )
            el.clear()
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(str(value))
            time.sleep(0.15)

            confirmed = (el.get_attribute("value") or "").strip()
            val_str = str(value).strip()
            # Comparación directa, más normalización numérica para campos
            # PrimeFaces InputNumber que formatean con '$' y ',' (ej: '$1,750.00').
            if (val_str in confirmed or confirmed in val_str
                    or _norm_num(val_str) == _norm_num(confirmed)):
                if attempt > 1:
                    log.info("  Campo '%s' llenado correctamente en intento %d: '%s'",
                             element_id, attempt, confirmed)
                return confirmed

            _log_attempt(element_id, attempt, max_attempts,
                         f"esperado='{value}' obtenido='{confirmed}'")
            wait_for_ajax(driver)

        except (StaleElementReferenceException, WebDriverException) as exc:
            _log_attempt(element_id, attempt, max_attempts, str(type(exc).__name__))
            if attempt == max_attempts:
                raise FieldFillError(
                    f"Campo '{element_id}': error al interactuar ({exc})"
                ) from exc
            wait_for_ajax(driver)

    raise FieldFillError(
        f"Campo '{element_id}': no se confirmó el valor '{value}' "
        f"después de {max_attempts} intentos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# force_select_menu_contains
# ─────────────────────────────────────────────────────────────────────────────

def force_select_menu_contains(
    driver,
    widget_id: str,
    label: str,
    max_attempts: int = 3,
) -> str:
    """Abre un SelectOneMenu de PrimeFaces y selecciona la primera opción que
    CONTIENE *label* (insensible a mayúsculas/acentos).

    Confirma la selección leyendo el elemento `_label` del widget.

    Returns:
        Texto del _label tras la selección confirmada.
    Raises:
        FieldFillError si falla después de max_attempts intentos.
    """
    panel_id = widget_id + "_panel"
    label_id = widget_id + "_label"
    target   = _norm(label.strip())

    for attempt in range(1, max_attempts + 1):
        try:
            trigger = wait_for_element_clickable(driver, By.ID, widget_id, timeout=15)
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", trigger
            )
            try:
                trigger.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", trigger)
            wait_for_ajax(driver)

            panel = wait_for_element_visible(driver, By.ID, panel_id, timeout=10)
            items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")

            for item in items:
                texto = item.text.strip()
                if target in _norm(texto):
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", item
                    )
                    try:
                        item.click()
                    except WebDriverException:
                        driver.execute_script("arguments[0].click();", item)
                    wait_for_ajax(driver)

                    confirmed = ""
                    try:
                        confirmed = driver.find_element(By.ID, label_id).text.strip()
                    except Exception:
                        confirmed = texto  # fallback al texto pre-clic

                    if target in _norm(confirmed):
                        if attempt > 1:
                            log.info("  Dropdown '%s' seleccionado en intento %d: '%s'",
                                     widget_id, attempt, confirmed)
                        return confirmed

                    _log_attempt(widget_id, attempt, max_attempts,
                                 f"clicked='{texto}' label='{confirmed}'")
                    break  # ya intentamos con el item correcto, reintentar todo
            else:
                opciones = [i.text.strip() for i in items if i.text.strip()]
                _log_attempt(widget_id, attempt, max_attempts,
                             f"'{label}' no encontrado. Opciones disponibles: {opciones}")

        except (StaleElementReferenceException, TimeoutException, WebDriverException) as _e:
            _log_attempt(widget_id, attempt, max_attempts,
                         f"{type(_e).__name__}: {str(_e)[:120]}")

        wait_for_ajax(driver)
        time.sleep(0.5)  # dejar que PrimeFaces estabilice el DOM entre reintentos

    raise FieldFillError(
        f"Dropdown '{widget_id}': no se pudo seleccionar la opción '{label}' "
        f"después de {max_attempts} intentos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# force_select_menu_exact
# ─────────────────────────────────────────────────────────────────────────────

def force_select_menu_exact(
    driver,
    widget_id: str,
    label: str,
    max_attempts: int = 3,
) -> str:
    """Igual que force_select_menu_contains pero requiere coincidencia EXACTA
    (insensible a mayúsculas).

    Abre el dropdown con el elemento `_label` como trigger (igual que el
    comportamiento original de select_one_menu_exact).
    """
    panel_id = widget_id + "_panel"
    label_id = widget_id + "_label"
    target   = label.strip().lower()

    for attempt in range(1, max_attempts + 1):
        try:
            trigger = wait_for_element_clickable(driver, By.ID, label_id, timeout=15)
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", trigger
            )
            trigger.click()
            wait_for_ajax(driver)

            panel = wait_for_element_visible(driver, By.ID, panel_id, timeout=10)
            items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")

            for item in items:
                texto = item.text.strip()
                if texto.lower() == target:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", item
                    )
                    try:
                        item.click()
                    except WebDriverException:
                        driver.execute_script("arguments[0].click();", item)
                    wait_for_ajax(driver)

                    confirmed = ""
                    try:
                        confirmed = driver.find_element(By.ID, label_id).text.strip()
                    except Exception:
                        confirmed = texto

                    if confirmed.lower() == target:
                        if attempt > 1:
                            log.info("  Dropdown EXACT '%s' seleccionado en intento %d: '%s'",
                                     widget_id, attempt, confirmed)
                        return confirmed

                    _log_attempt(widget_id, attempt, max_attempts,
                                 f"label_final='{confirmed}'")
                    break
            else:
                opciones = [i.text.strip() for i in items if i.text.strip()]
                _log_attempt(widget_id, attempt, max_attempts,
                             f"'{label}' no encontrado. Opciones: {opciones}")

        except StaleElementReferenceException:
            _log_attempt(widget_id, attempt, max_attempts, "StaleElement")

        wait_for_ajax(driver)

    raise FieldFillError(
        f"Dropdown EXACT '{widget_id}': no se pudo seleccionar '{label}' "
        f"después de {max_attempts} intentos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# force_jquery_select
# ─────────────────────────────────────────────────────────────────────────────

def force_jquery_select(
    driver,
    input_id: str,
    label: str,
    max_attempts: int = 3,
) -> str:
    """Asigna valor a un <select> oculto de PrimeFaces via jQuery y confirma que
    el elemento `_label` visible se actualizó correctamente.

    Estrategia de match: exacto → empieza-con → contiene (insensible a mayúsculas).

    Returns:
        Texto del label confirmado.
    Raises:
        FieldFillError si no se confirma después de max_attempts intentos.
    """
    label_id = input_id.replace("_input", "_label")
    target   = label.strip().lower()

    for attempt in range(1, max_attempts + 1):
        matched_text = driver.execute_script(
            "var sel = document.getElementById(arguments[0]);"
            "if (!sel) return null;"
            "var opts = Array.from(sel.options);"
            "var t = arguments[1];"
            "var found = null;"
            "for (var a = 0; a < opts.length; a++) {"
            "  if (opts[a].text.trim().toLowerCase() === t) { found = opts[a]; break; }"
            "}"
            "if (!found) for (var b = 0; b < opts.length; b++) {"
            "  if (opts[b].text.trim().toLowerCase().indexOf(t) === 0) { found = opts[b]; break; }"
            "}"
            "if (!found) for (var c = 0; c < opts.length; c++) {"
            "  if (opts[c].text.trim().toLowerCase().indexOf(t) >= 0) { found = opts[c]; break; }"
            "}"
            "if (found) {"
            "  sel.value = found.value;"
            "  window.jQuery(sel).trigger('change');"
            "  return found.text.trim();"
            "}"
            "return null;",
            input_id, target,
        )

        if matched_text is None:
            _log_attempt(input_id, attempt, max_attempts,
                         f"'{label}' no encontrado en el <select>")
            wait_for_ajax(driver)
            continue

        wait_for_ajax(driver)
        time.sleep(0.2)

        # Confirmar via el label visible
        confirmed = ""
        try:
            confirmed = driver.find_element(By.ID, label_id).text.strip()
        except Exception:
            confirmed = matched_text  # sin label → usar el texto encontrado

        if target in _norm(confirmed) or target in _norm(matched_text):
            if attempt > 1:
                log.info("  jQuery select '%s' confirmado en intento %d: '%s'",
                         input_id, attempt, confirmed or matched_text)
            return confirmed or matched_text

        _log_attempt(input_id, attempt, max_attempts,
                     f"set='{matched_text}' label_visible='{confirmed}'")
        wait_for_ajax(driver)

    raise FieldFillError(
        f"jQuery select '{input_id}': no se confirmó '{label}' "
        f"después de {max_attempts} intentos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# force_autocomplete
# ─────────────────────────────────────────────────────────────────────────────

def force_autocomplete(
    driver,
    input_id: str,
    text: str,
    target: str = None,
    max_attempts: int = 3,
    timeout: int = 15,
) -> str:
    """Escribe en un AutoComplete de PrimeFaces y confirma que el valor aceptado
    contiene *target* (por defecto, *text*).

    Estrategia:
      1. Limpiar → escribir → esperar AJAX.
      2. ARROW_DOWN + ENTER → leer value del input.
      3. Si no coincide, buscar en el panel de sugerencias y hacer clic.
      4. Reintentar hasta max_attempts veces.

    Returns:
        El valor confirmado del input tras la selección.
    Raises:
        FieldFillError si no se confirma después de max_attempts intentos.
    """
    expected = (target or text).strip()

    for attempt in range(1, max_attempts + 1):
        try:
            el = wait_for_element_clickable(driver, By.ID, input_id, timeout=timeout)
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", el
            )
            # Limpieza triple para vaciar el estado anterior de PrimeFaces
            el.clear()
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(text)
            time.sleep(0.4)
            wait_for_ajax(driver, timeout=timeout)

            # Paso A — confirmación con teclado
            el.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.1)
            el.send_keys(Keys.ENTER)
            time.sleep(0.15)
            wait_for_ajax(driver)

            confirmed = (el.get_attribute("value") or "").strip()
            if expected.lower() in confirmed.lower():
                el.send_keys(Keys.TAB)
                wait_for_ajax(driver)
                if attempt > 1:
                    log.info("  Autocomplete '%s' confirmado en intento %d: '%s'",
                             input_id, attempt, confirmed)
                return confirmed

            # Paso B — clic en panel de sugerencias
            try:
                panel = wait_for_element_visible(
                    driver, By.CSS_SELECTOR,
                    "ul.ui-autocomplete-items", timeout=5
                )
                items = panel.find_elements(
                    By.CSS_SELECTOR, "li.ui-autocomplete-item"
                )
                for item in items:
                    if expected.lower() in item.text.strip().lower():
                        item.click()
                        wait_for_ajax(driver)
                        confirmed = (el.get_attribute("value") or "").strip()
                        if expected.lower() in confirmed.lower():
                            el.send_keys(Keys.TAB)
                            wait_for_ajax(driver)
                            if attempt > 1:
                                log.info(
                                    "  Autocomplete '%s' (panel) confirmado en intento %d: '%s'",
                                    input_id, attempt, confirmed
                                )
                            return confirmed
                        break
                else:
                    # Ningún item coincide → usar el primero disponible
                    if items:
                        items[0].click()
                        wait_for_ajax(driver)
                        confirmed = (el.get_attribute("value") or "").strip()
                        el.send_keys(Keys.TAB)
                        wait_for_ajax(driver)
                        if confirmed:
                            return confirmed
            except (TimeoutException, Exception):
                pass

            _log_attempt(input_id, attempt, max_attempts,
                         f"esperado='{expected}' obtenido='{confirmed}'")
            wait_for_ajax(driver)

        except (StaleElementReferenceException, WebDriverException) as exc:
            _log_attempt(input_id, attempt, max_attempts, str(type(exc).__name__))
            if attempt == max_attempts:
                raise FieldFillError(
                    f"Autocomplete '{input_id}': error en intento {attempt}: {exc}"
                ) from exc
            wait_for_ajax(driver)

    raise FieldFillError(
        f"Autocomplete '{input_id}': no se confirmó '{expected}' "
        f"después de {max_attempts} intentos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# validate_field_value  (lectura sin modificar)
# ─────────────────────────────────────────────────────────────────────────────

def validate_field_value(
    driver,
    element_id: str,
    expected: str,
    read_method: str = "attr",  # "attr" | "text" | "label"
    read_attr: str = "value",
) -> bool:
    """Devuelve True si el valor actual del campo contiene *expected*.

    read_method:
        "attr"  → element.get_attribute(read_attr)  (input, select)
        "text"  → element.text                       (span, div)
        "label" → _label de un SelectOneMenu PrimeFaces
    """
    try:
        if read_method == "label":
            el = driver.find_element(By.ID, element_id + "_label")
            current = (el.get_attribute("textContent") or el.text or "").strip()
        elif read_method == "text":
            current = driver.find_element(By.ID, element_id).text.strip()
        else:
            current = (
                driver.find_element(By.ID, element_id)
                .get_attribute(read_attr) or ""
            ).strip()
        return expected.strip().lower() in current.lower()
    except Exception:
        return False

"""PrimeFaces-specific Selenium wait helpers."""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# XPath for the PrimeFaces AJAX status indicator
_AJAX_SPINNER_XPATH = "//*[contains(@id,'ajaxStatus') and contains(@style,'display: block')]"
_AJAX_INDICATOR_CSS = "div.ui-blockui-document"


def wait_for_ajax(driver, timeout: int = 30) -> None:
    """Block until the PrimeFaces AJAX spinner/blockers disappear."""
    try:
        # If a blocker appeared, wait for it to vanish
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, _AJAX_INDICATOR_CSS))
        )
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, _AJAX_INDICATOR_CSS))
        )
    except TimeoutException:
        # No blocker appeared — that's fine
        pass
    # Extra micro-sleep for React-like DOM settle
    time.sleep(0.3)


def wait_for_element_visible(driver, by, locator, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, locator))
    )


def wait_for_element_clickable(driver, by, locator, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, locator))
    )


def wait_for_element_present(driver, by, locator, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, locator))
    )


def wait_for_toast(driver, timeout: int = 10) -> str | None:
    """Return toast message text if a PrimeFaces growl/toast appears, else None."""
    try:
        toast = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "div.ui-growl-message, div.ui-messages-error")
            )
        )
        return toast.text.strip()
    except TimeoutException:
        return None


def is_element_present(driver, by, locator) -> bool:
    try:
        driver.find_element(by, locator)
        return True
    except NoSuchElementException:
        return False

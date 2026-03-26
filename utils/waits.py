"""Selenium wait helpers."""
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

_log = logging.getLogger("waits")


def wait_for_ajax(driver, timeout: int = 2) -> None:
    """Espera a que desaparezca el overlay de bloqueo AJAX (div.ui-blockui-document)."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-blockui-document"))
        )
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.ui-blockui-document"))
        )
    except TimeoutException:
        pass


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

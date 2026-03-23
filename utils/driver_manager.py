"""Chrome WebDriver factory using Selenium Manager (built-in, no extra library)."""
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_driver(download_dir: str) -> webdriver.Chrome:
    abs_download = os.path.abspath(download_dir)
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    # Evitar que Chrome muestre confirmación "Descargar archivo inseguro"
    options.add_argument("--safebrowsing-disable-download-protection")
    options.add_argument("--disable-download-restrictions")
    options.add_experimental_option("prefs", {
        "download.default_directory": abs_download,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection_for_test_content_enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.content_settings.exceptions.automatic_downloads": {
            "[*.]": {"setting": 1}
        },
    })
    # Selenium 4.6+ incluye Selenium Manager que descarga chromedriver
    # automáticamente sin necesitar webdriver-manager.
    driver = webdriver.Chrome(options=options)
    # Instruir al DevTools de Chrome para permitir todas las descargas sin
    # mostrar diálogo de confirmación (reemplaza Page.setDownloadBehavior).
    try:
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": abs_download,
            "eventsEnabled": True,
        })
    except Exception:
        pass
    return driver

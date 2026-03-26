"""Chrome WebDriver factory using Selenium Manager (built-in, no extra library)."""
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def create_driver(download_dir: str) -> webdriver.Chrome:
    abs_download = os.path.abspath(download_dir)
    options = Options()

    options.add_argument("--start-maximized")

    # ── Notificaciones / comportamiento de descarga ───────────────────────
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

    # Forzar a Selenium Manager a descargar el chromedriver correcto
    # ignorando cualquier versión incompatible que el equipo tenga en PATH.
    # Al pasar executable_path="" Selenium 4.6+ delega a su manager interno
    # que descarga el driver que coincide exactamente con la versión de Chrome
    # instalada en el sistema.
    service = Service()
    # Limpiar chromedriver del PATH de este proceso para que Selenium Manager
    # sea el único resolutor y no tome el driver viejo del sistema.
    env_path = os.environ.get("PATH", "")
    filtered_path = os.pathsep.join(
        p for p in env_path.split(os.pathsep)
        if "chromedriver" not in p.lower()
    )
    os.environ["PATH"] = filtered_path

    driver = webdriver.Chrome(service=service, options=options)

    # Restaurar PATH original para el resto del proceso
    os.environ["PATH"] = env_path

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

"""Chrome WebDriver factory using Selenium Manager (built-in, no extra library)."""
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_driver(download_dir: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })
    # Selenium 4.6+ incluye Selenium Manager que descarga chromedriver
    # automáticamente sin necesitar webdriver-manager.
    driver = webdriver.Chrome(options=options)
    return driver

"""pytest fixtures shared across all tests."""
import configparser
import os
import pytest

from utils.driver_manager import create_driver
from utils.excel_manager import ResultsWriter, read_conceptos
from utils.logger import get_logger

log = get_logger("conftest")

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE, "config", "config.ini")
_REPORTS_DIR = os.path.join(_BASE, "reports")
_SCREENSHOTS_DIR = os.path.join(_BASE, "screenshots")
_DOWNLOADS_DIR = os.path.join(_BASE, "downloads")


# ── Config ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def config():
    cfg = configparser.ConfigParser()
    cfg.read(_CONFIG_PATH, encoding="utf-8")
    return cfg


# ── Driver ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def driver(config):
    drv = create_driver(_DOWNLOADS_DIR)
    drv.implicitly_wait(int(config["timeouts"].get("implicit", 5)))
    yield drv
    drv.quit()


# ── Login (session-scoped — login once) ──────────────────────────────────────

@pytest.fixture(scope="session")
def logged_in_driver(driver, config):
    from pages.login_page import LoginPage
    login = LoginPage(driver)
    login.login(
        login_url=config["app"]["login_url"],
        username=config["credentials"]["username"],
        password=config["credentials"]["password"],
    )
    log.info("Session login complete")
    return driver


# ── Conceptos data ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def conceptos_data(config):
    excel_path = config["data"]["conceptos_excel"]
    # Resolve relative to workspace root if not absolute
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(_BASE, excel_path)
    log.info("Loading conceptos from: %s", excel_path)
    return read_conceptos(excel_path)  # (List[ConceptoRow], List[ImpuestoRow])


# ── Results writer (session-scoped) ──────────────────────────────────────────

@pytest.fixture(scope="session")
def results_writer():
    writer = ResultsWriter(_REPORTS_DIR)
    yield writer
    path = writer.save()
    log.info("Results saved to: %s", path)
    print(f"\n✅ Resultados guardados en: {path}")


# ── Shared state between tests (UUID of the PPD factura) ─────────────────────

@pytest.fixture(scope="session")
def shared_state():
    return {
        "uuid_factura": "855fe4f0-ee8a-45c9-97eb-b2d772af9c4a",
        "total_factura": 116.00,
        "uuid_comp1": None,
        "saldo_insoluto_comp1": 0.0,
    }

@pytest.fixture(scope="session")
def shared_state():
    return {
        "uuid_factura": "855fe4f0-ee8a-45c9-97eb-b2d772af9c4a",
        "total_factura": 116.00,
        "uuid_comp1": None,
        "saldo_insoluto_comp1": 0.0,
    }

# ── Utility paths ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def screenshots_dir():
    os.makedirs(_SCREENSHOTS_DIR, exist_ok=True)
    return _SCREENSHOTS_DIR


@pytest.fixture(scope="session")
def downloads_dir():
    os.makedirs(_DOWNLOADS_DIR, exist_ok=True)
    return _DOWNLOADS_DIR

# ── UUID RELACIONADO  ───────────────────────────────────────────────────
"""pytest fixtures shared across all tests."""
import configparser
import os
import pytest

from utils.driver_manager import create_driver
from utils.excel_manager import ResultsWriter, read_conceptos, read_pagos, read_escenarios
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
        "uuid_factura": None,       # Establecido por test_01 tras el timbrado
        "total_factura": 0.0,
        "uuid_comp1": None,
        "saldo_insoluto_comp1": 0.0,
    }


# ── Pagos data (from Excel 'pagos' sheet) ─────────────────────────────────────

@pytest.fixture(scope="session")
def pagos_data(config):
    excel_path = config["data"]["conceptos_excel"]
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(_BASE, excel_path)
    log.info("Loading pagos from: %s", excel_path)
    return read_pagos(excel_path)


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


# ── Escenarios de impuestos (parametrizados desde Excel) ─────────────────────

@pytest.fixture(scope="session")
def escenarios_data(config):
    """Lista de EscenarioData leída del Excel.  Usada por pytest_generate_tests."""
    excel_path = config["data"]["conceptos_excel"]
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(_BASE, excel_path)
    log.info("Loading escenarios from: %s", excel_path)
    return read_escenarios(excel_path)


def pytest_generate_tests(metafunc):
    """Parametriza automáticamente 'escenario' con cada fila del Excel.

    Cualquier función de test que declare el parámetro 'escenario' recibirá
    una instancia de EscenarioData por cada escenario definido en el Excel,
    generando un caso de prueba independiente por escenario.
    """
    if "escenario" not in metafunc.fixturenames:
        return

    cfg = configparser.ConfigParser()
    cfg.read(_CONFIG_PATH, encoding="utf-8")
    excel_path = cfg["data"]["conceptos_excel"]
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(_BASE, excel_path)

    try:
        escenarios = read_escenarios(excel_path)
    except Exception as exc:
        log.error("pytest_generate_tests: no se pudo leer escenarios del Excel: %s", exc)
        escenarios = []

    if not escenarios:
        # Sin escenarios: genera un test que será skipeado agraciosamente
        metafunc.parametrize("escenario", [None], ids=["sin_escenarios"])
        return

    metafunc.parametrize(
        "escenario",
        escenarios,
        ids=[
            f"esc{e.id_escenario}_{e.nombre.replace(' ', '_').replace(',', '')}"
            for e in escenarios
        ],
    )
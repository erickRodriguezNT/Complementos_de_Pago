"""Logger with rotating file handler + console output.

Funciones adicionales:
    init_run_logger(run_dir)  — añade un FileHandler por ejecución en outputs/
    log_section(logger, title, status="")  — banner ═══ INICIO / FIN ═══
    log_step(logger, n, description, level="info")  — línea numerada de paso
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from utils.paths import LOGS_DIR as LOG_DIR

# Marca temporal única por proceso — todos los loggers de la misma ejecución
# comparten este valor para que los archivos de log sean consistentes.
_RUN_TS: str = datetime.now().strftime("%Y%m%d_%H%M%S")

# Identificador del FileHandler por ejecución (para no duplicar al reiniciar fixtures)
_RUN_HANDLER_ID = "cfdi_run_file_handler"


def get_logger(name: str = "cfdi_automation") -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, f"run_{_RUN_TS}.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Per-execution log in outputs/ dir
# ─────────────────────────────────────────────────────────────────────────────

def init_run_logger(run_dir: str) -> None:
    """Agrega un FileHandler al logger raíz 'cfdi_automation' que escribe
    en *run_dir*/ejecucion_<ts>.log  (un archivo por ejecución de pytest).

    Usa un atributo personalizado en el handler para evitar duplicados si
    la fixture de pytest la llama más de una vez.
    """
    root = logging.getLogger("cfdi_automation")
    # Evitar duplicados
    for h in root.handlers:
        if getattr(h, "_cfdi_run_id", None) == _RUN_TS:
            return

    os.makedirs(run_dir, exist_ok=True)
    log_path = os.path.join(run_dir, f"ejecucion_{_RUN_TS}.log")

    human_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    )
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(human_fmt)
    fh.setLevel(logging.DEBUG)
    fh._cfdi_run_id = _RUN_TS  # type: ignore[attr-defined]

    root.addHandler(fh)
    root.info("═" * 72)
    root.info("  INICIO EJECUCIÓN — %s", _RUN_TS)
    root.info("  Log: %s", log_path)
    root.info("═" * 72)


# ─────────────────────────────────────────────────────────────────────────────
# Banner helpers
# ─────────────────────────────────────────────────────────────────────────────

_BANNER_WIDTH = 72


def log_section(logger: logging.Logger, title: str, status: str = "") -> None:
    """Imprime un banner horizontal con el título del escenario/sección.

    Ejemplos:
        log_section(log, "ESCENARIO 05 — IVA 16% TRASLADO")
        log_section(log, "ESCENARIO 05 — IVA 16% TRASLADO", status="PASS")
        log_section(log, "ESCENARIO 05 — IVA 16% TRASLADO", status="FAIL")
    """
    sep = "═" * _BANNER_WIDTH
    label = f"  {title}"
    if status:
        label += f"  [{status}]"
    logger.info(sep)
    logger.info(label)
    logger.info(sep)


def log_step(
    logger: logging.Logger,
    n,
    description: str,
    level: str = "info",
    status: str = "",
) -> None:
    """Imprime una línea numerada de paso.

    Ejemplo:
        log_step(log, 1, "Factura PPD")
        →   [INFO]    ── Paso 1 — Factura PPD
        log_step(log, 1, "Factura PPD", status="PASS")
        →   [INFO]    ── Paso 1 — Factura PPD  [PASS]
    """
    suffix = f"  [{status}]" if status else ""
    line = f"  ── Paso {n} — {description}{suffix}"
    getattr(logger, level.lower(), logger.info)(line)

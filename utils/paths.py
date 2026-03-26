"""
Portable BASE_DIR resolver.

Works correctly in three modes:
  1. Normal development  — run from the project root with `python run_tests.py`
  2. PyInstaller onedir  — the .exe sits next to data/, config.ini, outputs/
  3. PyInstaller onefile — the .exe is a single file; _MEIPASS holds temp files
                           but we NEVER write there; everything uses exe's folder

Rule: user-facing folders (data, outputs, logs, config.ini) always live next to
      the .exe (or next to run_tests.py in dev mode).  Source code and compiled
      bytecode go inside the PyInstaller bundle and are invisible to the user.
"""
import os
import sys


def _resolve_base() -> str:
    """Return the directory that contains the user-visible files.

    Priority:
      • PyInstaller frozen (onefile OR onedir) → folder of the .exe
      • Development                            → parent of this file (cfdi-automation/)
    """
    if getattr(sys, "frozen", False):
        # sys.executable is the .exe path in both onefile and onedir modes
        return os.path.dirname(os.path.abspath(sys.executable))
    # Development: this file lives at cfdi-automation/utils/paths.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR: str = _resolve_base()

# ── User-facing directories ───────────────────────────────────────────────────
DATA_DIR    = os.path.join(BASE_DIR, "data")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

# Legacy path kept for conftest that still looks inside config/
CONFIG_DIR      = os.path.join(BASE_DIR, "config")
CONFIG_INI_PATH = os.path.join(CONFIG_DIR, "config.ini")


def get_data_file(filename: str) -> str:
    """Return absolute path to a file inside the data/ folder."""
    return os.path.join(DATA_DIR, filename)


def ensure_dirs():
    """Create all required runtime directories if they do not exist."""
    for d in (DATA_DIR, OUTPUTS_DIR, LOGS_DIR, REPORTS_DIR, CONFIG_DIR):
        os.makedirs(d, exist_ok=True)

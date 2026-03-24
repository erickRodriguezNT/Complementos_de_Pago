"""Helpers for organizing test output into per-run / per-escenario folders.

Run layout:
    outputs/
    └── ejecucion_YYYYMMDD_HHMMSS/
        ├── escenario_01_IVA_16/
        │   ├── before_timbrar_esc1_ppd_<ts>.png
        │   ├── 2026-...-FP-<uuid>.zip
        │   └── ...
        ├── escenario_02_IVA_0/
        │   └── ...
        └── ...
"""
import os
import re
from datetime import datetime


def make_run_dir(base: str) -> str:
    """Create and return outputs/ejecucion_YYYYMMDD_HHMMSS/ under *base*."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(base, f"ejecucion_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def make_escenario_dir(run_dir: str, esc_id: int, esc_nombre: str) -> str:
    """Create and return escenario_NN_<nombre>/ under *run_dir*."""
    safe = re.sub(r"[^\w\-]", "_", esc_nombre).strip("_")[:50]
    path = os.path.join(run_dir, f"escenario_{esc_id:02d}_{safe}")
    os.makedirs(path, exist_ok=True)
    return path

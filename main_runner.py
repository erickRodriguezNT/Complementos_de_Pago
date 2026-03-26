"""
main_runner.py — PyInstaller entry point for AutoCFDI.exe

Usage (end user):
  Double-click AutoCFDI.exe              → runs all 22 scenarios
  AutoCFDI.exe --escenario 5             → runs only scenario 5
  AutoCFDI.exe --escenarios 1 3 5 12    → runs listed scenarios

Usage (developer):
  python main_runner.py [--escenario N | --escenarios N1 N2 ...]
"""
import argparse
import os
import sys
from datetime import datetime

# ── Ensure utils/ is importable when running as .exe ─────────────────────────
if not getattr(sys, "frozen", False):
    _project_root = os.path.dirname(os.path.abspath(__file__))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

from utils.paths import BASE_DIR, REPORTS_DIR, DATA_DIR, OUTPUTS_DIR, ensure_dirs  # noqa: E402

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ensure_dirs()

# ── Parse scenario arguments ──────────────────────────────────────────────────
_parser = argparse.ArgumentParser(add_help=False)
_group = _parser.add_mutually_exclusive_group()
_group.add_argument("--escenario",  type=int, default=None)
_group.add_argument("--escenarios", type=int, nargs="+", default=None)
_args, _unknown = _parser.parse_known_args()

if _args.escenario is not None:
    _selected_ids = [_args.escenario]
elif _args.escenarios:
    _selected_ids = _args.escenarios
else:
    _selected_ids = []   # empty → run all

# ── Resolve tests / rootdir for pytest ───────────────────────────────────────
if getattr(sys, "frozen", False):
    _bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    _tests_file = os.path.join(_bundle_dir, "tests", "test_escenarios_impuestos.py")
    _pytest_ini = os.path.join(_bundle_dir, "pytest.ini")
else:
    _bundle_dir = BASE_DIR
    _tests_file = os.path.join(BASE_DIR, "tests", "test_escenarios_impuestos.py")
    _pytest_ini = os.path.join(BASE_DIR, "pytest.ini")

html_report = os.path.join(
    REPORTS_DIR,
    f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
)

# ── Check optional plugins ─────────────────────────────────────────────────
# pytest-html uses module-level StashKey singletons that break when loaded
# inside a PyInstaller bundle (duplicate module paths → different key objects).
# In frozen mode we skip --html entirely; results are in the Excel + outputs/.
_is_frozen = getattr(sys, "frozen", False)
try:
    import pytest_html as _ph  # noqa: F401
    _has_pytest_html = not _is_frozen  # only use it in dev mode
except ImportError:
    _has_pytest_html = False

# ── Banner ────────────────────────────────────────────────────────────────────
separator = "=" * 62
print(separator)
print("  AutoCFDI — Automatizacion CFDI 4.0 (PPD + CP1 + CP2)")
print(separator)
print(f"  Carpeta base : {BASE_DIR}")
print(f"  Datos Excel  : {DATA_DIR}")
print(f"  Resultados   : {OUTPUTS_DIR}")
if _selected_ids:
    _ids_str = ", ".join(str(n) for n in _selected_ids)
    print(f"  Escenarios   : {_ids_str}")
else:
    print("  Escenarios   : TODOS (1-22)")
if _has_pytest_html:
    print(f"  Reporte HTML : {html_report}")
print(separator)
print()

# ── Run pytest via its Python API (no subprocess) ────────────────────────────
import pytest  # noqa: E402

# Build args list
_pytest_args = [
    _tests_file,
    "-v",
    "-s",
    "-p", "no:warnings",
    # Explicitly point pytest at the bundled ini so it doesn't walk up
    # the directory tree and pick up the source-project's pytest.ini
    "-c", _pytest_ini,
    "--import-mode=importlib",
]

if _has_pytest_html:
    _pytest_args += [
        f"--html={html_report}",
        "--self-contained-html",
    ]
else:
    if _is_frozen:
        print("  [INFO] Reporte HTML deshabilitado en modo ejecutable.")
        print("         Resultados disponibles en outputs/ y reports/ (Excel).")
    else:
        print("  [INFO] pytest-html no instalado — reporte HTML omitido")
    print()

# ── Apply scenario filter (-k) ────────────────────────────────────────────────
# Test IDs have format: esc{N}_{nombre}  (e.g. esc1_IVA_16, esc10_IVA_16_...)
# Using "escN_" with trailing underscore avoids false matches (esc1 vs esc10).
if _selected_ids:
    _k_filter = " or ".join(f"esc{n}_" for n in _selected_ids)
    _pytest_args += ["-k", _k_filter]

exit_code = pytest.main(_pytest_args)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print(separator)
if exit_code == 0:
    print("  RESULTADO: TODOS LOS ESCENARIOS PASARON")
else:
    print(f"  RESULTADO: ALGUNOS ESCENARIOS FALLARON (codigo {exit_code})")
if _has_pytest_html:
    print(f"  Reporte HTML : {html_report}")
print(f"  Evidencias   : {OUTPUTS_DIR}")
print(separator)

if getattr(sys, "frozen", False):
    input("\nPresiona ENTER para cerrar...")

sys.exit(exit_code)


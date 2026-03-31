"""
main_runner.py — PyInstaller entry point for AutoCFDI.exe

Usage (end user / double-click):
  AutoCFDI.exe              → abre interfaz interactiva para seleccionar escenarios

Usage (batch / CLI):
  AutoCFDI.exe --escenario 5             → ejecuta solo el escenario 5
  AutoCFDI.exe --escenarios 1 3 5 12    → ejecuta los escenarios indicados

Usage (developer):
  python main_runner.py                          → interfaz interactiva
  python main_runner.py --escenario N            → escenario único
  python main_runner.py --escenarios N1 N2 ...  → varios escenarios
"""
import argparse
import configparser
import os
import sys
from datetime import datetime

# ── Ensure utils/ is importable when running as .exe ─────────────────────────
if not getattr(sys, "frozen", False):
    _project_root = os.path.dirname(os.path.abspath(__file__))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

from utils.paths import BASE_DIR, REPORTS_DIR, DATA_DIR, OUTPUTS_DIR, CONFIG_INI_PATH, ensure_dirs  # noqa: E402

# ── Bootstrap ────────────────────────────────────────────────────────────────────────────────
ensure_dirs()


# ── Carga dinámica de escenarios desde el Excel ──────────────────────────────────
def _load_escenarios() -> list:
    """Lee el Excel y devuelve la lista de EscenarioData."""
    from utils.excel_manager import read_escenarios  # import local para evitar ciclos
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_INI_PATH, encoding="utf-8")
    try:
        excel_path = cfg["data"]["conceptos_excel"]
        if not os.path.isabs(excel_path):
            excel_path = os.path.join(BASE_DIR, excel_path)
        return read_escenarios(excel_path)
    except Exception as exc:
        print(f"  [WARN] No se pudo leer los escenarios del Excel: {exc}")
        return []


# ── Interfaz interactiva de selección ───────────────────────────────────────────────
def _interactive_scenario_selection(escenarios: list) -> list:
    """Muestra el menú interactivo con nombre de escenarios y devuelve los IDs.

    Retorna lista vacía  →  ejecutar todos.
    Retorna [id1, id2…] →  ejecutar solo esos escenarios.
    """
    if not escenarios:
        print("  [WARN] No se encontraron escenarios en el Excel.  Verifique el archivo.")
        return []

    n = len(escenarios)
    valid_ids = {e.id_escenario for e in escenarios}

    while True:
        sep = "=" * 62
        print()
        print(sep)
        print("  AutoCFDI — Seleccion de Escenarios")
        print(sep)
        print()
        for e in escenarios:
            print(f"  [{e.id_escenario:2d} ] ESC {e.id_escenario:02d} - {e.nombre}")
        print()
        print("  [a]   Seleccionar escenarios específicos (ej: 1,3,5)")
        print("  [b]   Ejecutar TODOS los escenarios")
        print("  [c]   Salir")
        print()
        entrada = input("  Su elección: ").strip().lower()

        # Opción c: salir
        if entrada == "c":
            print("\n  Saliendo...")
            sys.exit(0)

        # Opción b: ejecutar todos
        if entrada == "b":
            return []

        # Opción a: múltiples escenarios específicos
        if entrada == "a":
            while True:
                multi = input(
                    "  Ingrese números de escenarios separados por coma (ej: 1,3,5): "
                ).strip()
                try:
                    ids = [int(x.strip()) for x in multi.split(",") if x.strip()]
                    if not ids:
                        print("  [!] No se ingresaron escenarios.  Intente de nuevo.")
                        continue
                    invalid = [i for i in ids if i not in valid_ids]
                    if invalid:
                        print(f"  [!] IDs no encontrados: {invalid}.  Válidos: {sorted(valid_ids)}")
                        continue
                    return ids
                except ValueError:
                    print("  [!] Ingrese solo números enteros separados por coma.")

        print("  [!] Entrada no válida.  Ingrese 'a', 'b' o 'c'.")

# ── Parse scenario arguments ──────────────────────────────────────────────────
_parser = argparse.ArgumentParser(add_help=False)
_group = _parser.add_mutually_exclusive_group()
_group.add_argument("--escenario",  type=int, default=None)
_group.add_argument("--escenarios", type=int, nargs="+", default=None)
_args, _unknown = _parser.parse_known_args()

# Cargar escenarios una sola vez (para UI y banner)
_escenarios_list = _load_escenarios()
_n_escenarios = len(_escenarios_list)

if _args.escenario is not None:
    _selected_ids = [_args.escenario]
elif _args.escenarios:
    _selected_ids = _args.escenarios
else:
    # Sin argumentos CLI → mostrar interfaz interactiva
    _selected_ids = _interactive_scenario_selection(_escenarios_list)

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
print("  AutoCFDI — Automatizacion CFDI 4.0 (PPD + Complementos de Pago)")
print(separator)
print(f"  Carpeta base : {BASE_DIR}")
print(f"  Datos Excel  : {DATA_DIR}")
print(f"  Resultados   : {OUTPUTS_DIR}")
if _selected_ids:
    _ids_str = ", ".join(str(n) for n in _selected_ids)
    print(f"  Escenarios   : {_ids_str}")
else:
    print(f"  Escenarios   : TODOS (1-{_n_escenarios})")
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


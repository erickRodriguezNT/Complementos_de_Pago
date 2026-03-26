"""
Entry point: python run_tests.py
Runs the PPD + Complementos de Pago suite and prints the results file path.
"""
import os
import sys
import subprocess
from datetime import datetime

from utils.paths import BASE_DIR, REPORTS_DIR, ensure_dirs

ensure_dirs()

html_report = os.path.join(
    REPORTS_DIR, f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
)

# When running from inside a PyInstaller bundle the test files are extracted
# to a subfolder in the temp dir. We pass the absolute path explicitly so
# pytest can find them regardless of cwd.
TESTS_DIR = os.path.join(BASE_DIR, "tests") if not getattr(sys, "frozen", False) \
    else os.path.join(sys._MEIPASS, "tests")  # type: ignore[attr-defined]

cmd = [
    sys.executable, "-m", "pytest",
    os.path.join(TESTS_DIR, "test_escenarios_impuestos.py"),
    "-v",
    "-s",
    f"--html={html_report}",
    "--self-contained-html",
    "-p", "no:warnings",
]

print("=" * 60)
print("  CFDI Automation — Escenarios de Impuestos (PPD + CP1 + CP2)")
print("=" * 60)
print(f"Reporte HTML: {html_report}")
print()

result = subprocess.run(cmd, cwd=BASE_DIR)
sys.exit(result.returncode)

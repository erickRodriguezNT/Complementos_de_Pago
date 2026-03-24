"""
Entry point: python run_tests.py
Runs the PPD + Complementos de Pago suite and prints the results file path.
"""
import os
import sys
import subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE, "reports")
SCREENSHOTS_DIR = os.path.join(BASE, "screenshots")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

html_report = os.path.join(
    REPORTS_DIR, f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
)

cmd = [
    sys.executable, "-m", "pytest",
    "tests/test_escenarios_impuestos.py",
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

result = subprocess.run(cmd, cwd=BASE)
sys.exit(result.returncode)

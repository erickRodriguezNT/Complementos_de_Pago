"""
Script de diagnóstico: selecciona el Emisor RFC y guarda el HTML resultante
para identificar los IDs reales de Sucursal y Centro de Consumo.

Uso: python debug_emisor.py
Resultado: debug_output/page_after_emisor.html
"""
import os
import sys
import configparser
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = os.path.dirname(os.path.abspath(__file__))
cfg = configparser.ConfigParser()
cfg.read(os.path.join(BASE, "config", "config.ini"), encoding="utf-8")

OUT_DIR = os.path.join(BASE, "debug_output")
os.makedirs(OUT_DIR, exist_ok=True)

options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

try:
    # 1. Login
    print("Abriendo login...")
    driver.get(cfg["app"]["login_url"])
    time.sleep(8)  # esperar carga inicial

    # Guardar HTML de login para ver IDs reales
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "login_page.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("✅ HTML login guardado: debug_output/login_page.html")

    # Buscar campo usuario con fallbacks
    try:
        user_el = driver.find_element(By.ID, "loginForm:username")
    except Exception:
        try:
            user_el = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
        except Exception:
            user_el = driver.find_element(By.CSS_SELECTOR, "input[name*='user'], input[name*='User'], input[id*='user'], input[id*='User']")

    print(f"Campo usuario encontrado: id={user_el.get_attribute('id')}")
    user_el.send_keys(cfg["credentials"]["username"])

    try:
        pass_el = driver.find_element(By.ID, "loginForm:password")
    except Exception:
        pass_el = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    print(f"Campo password encontrado: id={pass_el.get_attribute('id')}")
    pass_el.send_keys(cfg["credentials"]["password"])

    try:
        btn = driver.find_element(By.ID, "loginForm:btnLogin")
    except Exception:
        btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
    print(f"Botón login encontrado: id={btn.get_attribute('id')}")
    btn.click()
    time.sleep(6)

    # 2. Ir a factura
    print("Abriendo formulario de factura...")
    driver.get(cfg["app"]["factura_url"])
    time.sleep(5)

    # 3. Guardar HTML inicial
    with open(os.path.join(OUT_DIR, "page_before_emisor.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("✅ HTML inicial guardado: debug_output/page_before_emisor.html")

    # 4. Seleccionar RFC Emisor
    print("Seleccionando RFC Emisor...")
    rfc = cfg["emisor"]["rfc"]
    trigger = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "formNuevaFactura:accordionDatosEmisor:selectOneEmisores"))
    )
    trigger.click()
    time.sleep(1)

    # Usar filtro si existe
    try:
        f_el = driver.find_element(By.ID, "formNuevaFactura:accordionDatosEmisor:selectOneEmisores_filter")
        f_el.send_keys(rfc)
        time.sleep(1)
    except Exception:
        pass

    panel = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(
            (By.ID, "formNuevaFactura:accordionDatosEmisor:selectOneEmisores_panel")
        )
    )
    items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")
    for item in items:
        if rfc in item.text:
            item.click()
            print(f"RFC {rfc} seleccionado")
            break

    # 5. Esperar AJAX
    print("Esperando carga de Sucursal/CC tras AJAX...")
    time.sleep(5)

    # 6. Guardar HTML después de seleccionar RFC
    with open(os.path.join(OUT_DIR, "page_after_emisor.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("✅ HTML post-emisor guardado: debug_output/page_after_emisor.html")

    # 7. Buscar todos los selectonemenu presentes y listar sus IDs
    print("\n=== SelectOneMenu encontrados en la página ===")
    selects = driver.find_elements(By.CSS_SELECTOR, "div.ui-selectonemenu")
    for s in selects:
        sid = s.get_attribute("id")
        label_el = s.find_elements(By.CSS_SELECTOR, ".ui-selectonemenu-label")
        label_txt = label_el[0].text if label_el else ""
        print(f"  ID: {sid!r:80s}  Valor actual: {label_txt!r}")

    # 8. Buscar inputs visibles (autoComplete, text inputs)
    print("\n=== Inputs visibles relacionados con Emisor ===")
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[id*='Emisor'], input[id*='emisor'], input[id*='Sucursal'], input[id*='sucursal'], input[id*='Centro'], input[id*='centro']")
    for inp in inputs:
        print(f"  INPUT id={inp.get_attribute('id')!r}  value={inp.get_attribute('value')!r}")

    # 9. Buscar específicamente el accordion del Emisor
    print("\n=== Elementos dentro del accordion Emisor ===")
    try:
        accordion = driver.find_element(By.ID, "formNuevaFactura:accordionDatosEmisor")
        selects_in_emisor = accordion.find_elements(By.CSS_SELECTOR, "div.ui-selectonemenu")
        for s in selects_in_emisor:
            sid = s.get_attribute("id")
            label_el = s.find_elements(By.CSS_SELECTOR, ".ui-selectonemenu-label")
            label_txt = label_el[0].text if label_el else ""
            print(f"  SELECT id={sid!r}  valor={label_txt!r}")
        inputs_in_emisor = accordion.find_elements(By.CSS_SELECTOR, "input:not([type='hidden'])")
        for inp in inputs_in_emisor:
            print(f"  INPUT  id={inp.get_attribute('id')!r}  name={inp.get_attribute('name')!r}")
    except Exception as e:
        print(f"  Error buscando accordion: {e}")

    print("\nRevisa debug_output/page_after_emisor.html para ver el HTML completo.")
    print("Busca 'PRUEBAS' o 'Pruebas' en ese archivo para localizar los IDs.")
    input("\nPresiona ENTER para cerrar el navegador...")

finally:
    driver.quit()

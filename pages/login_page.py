"""Login Page Object.

NOTE: Login URL and field IDs are PLACEHOLDERS — update after live inspection.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from utils.waits import wait_for_element_visible, wait_for_ajax
from utils.logger import get_logger

log = get_logger("login_page")

# ── Locators (update after live inspection) ──────────────────────────────────
_USER_INPUT    = "j_idt12:userName"
_PASS_INPUT    = "j_idt12:password"
_LOGIN_BUTTON  = "j_idt12:buttonLogin"
_LOGIN_CSS_ALT = "button[type='submit']"   # fallback


class LoginPage(BasePage):

    def login(self, login_url: str, username: str, password: str):
        log.info("Navigating to login: %s", login_url)
        self.driver.get(login_url)
        wait_for_ajax(self.driver)

        try:
            user_el = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, _USER_INPUT))
            )
        except Exception:
            user_el = self.driver.find_element(By.CSS_SELECTOR, "input[type='text']")

        user_el.clear()
        user_el.send_keys(username)

        try:
            pass_el = self.driver.find_element(By.ID, _PASS_INPUT)
        except Exception:
            pass_el = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")

        pass_el.clear()
        pass_el.send_keys(password)

        try:
            btn = self.driver.find_element(By.ID, _LOGIN_BUTTON)
        except Exception:
            btn = self.driver.find_element(By.CSS_SELECTOR, _LOGIN_CSS_ALT)

        btn.click()
        wait_for_ajax(self.driver, timeout=30)
        log.info("Login submitted for user '%s'", username)

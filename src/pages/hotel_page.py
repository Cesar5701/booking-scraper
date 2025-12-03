import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from booking_selectors import HotelPage as HotelPageSelectors, Reviews
from pages.reviews_modal import ReviewsModal

from pages.hotel_info_extractor import HotelInfoExtractor

class HotelPage:
    """
    Page Object para la página de detalles del hotel.
    """
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.info_extractor = HotelInfoExtractor(driver)

    def navigate(self, url: str):
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            logging.error(f"Timeout cargando la página del hotel: {url}")

    def get_name(self) -> str:
        """Delegado al extractor."""
        return self.info_extractor.get_name()

    def get_expected_review_count(self) -> int:
        """Obtiene el conteo total de reseñas esperado."""
        driver = self.driver
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, HotelPageSelectors.REVIEW_COUNT_LINKS)
            for elem in elements:
                text = elem.text
                import re
                match = re.search(r'\((\d+[\.,]?\d*)\)', text)
                if match:
                    num_str = match.group(1).replace('.', '').replace(',', '')
                    return int(num_str)
                    
            count_elem = driver.find_element(By.CSS_SELECTOR, HotelPageSelectors.REVIEW_COUNT_SIDEBAR)
            if count_elem:
                 text = count_elem.text
                 import re
                 match = re.search(r'(\d+[\.,]?\d*)', text)
                 if match:
                    num_str = match.group(1).replace('.', '').replace(',', '')
                    return int(num_str)
        except (NoSuchElementException, ValueError):
            pass
        return 0

    def open_reviews_modal(self) -> ReviewsModal:
        """Cierra popups y abre el modal de reseñas."""
        driver = self.driver
        
        # Cerrar popups
        try:
            WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, HotelPageSelectors.LOGIN_POPUP_CLOSE))
            ).click()
        except (TimeoutException, NoSuchElementException): pass

        # Abrir pestaña reseñas
        logging.info("      -> Intentando abrir panel de reseñas...")
        reviews_opened = False
        for by, selector in HotelPageSelectors.OPEN_REVIEWS_STRATEGIES:
            try:
                elem = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, selector)))
                driver.execute_script("arguments[0].click();", elem)
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, Reviews.ITEM))
                )
                reviews_opened = True
                logging.info(f"      [OK] Panel abierto usando: {selector}")
                break
            except (TimeoutException, ElementClickInterceptedException):
                continue
        
        if not reviews_opened:
            logging.warning("No se pudo abrir la pestaña de reseñas.")
            return None
            
        return ReviewsModal(driver, self.get_name(), driver.current_url)

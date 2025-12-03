import logging
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from booking_selectors import Reviews
from utils.cleaning import extract_score_from_text

class ReviewsModal:
    """
    Page Object para el modal/pestaña de reseñas.
    """
    def __init__(self, driver: webdriver.Chrome, hotel_name: str, hotel_url: str):
        self.driver = driver
        self.hotel_name = hotel_name
        self.hotel_url = hotel_url

    def _get_safe_text(self, element, selector: str) -> str:
        try:
            return element.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return ""

    def extract_current_page(self) -> List[Dict]:
        """Extrae las reseñas visibles en la página actual del modal."""
        try:
            review_elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, Reviews.ITEM))
            )
        except TimeoutException:
            logging.info("Tiempo de espera agotado buscando reseñas en esta página (posible fin).")
            return []

        page_reviews = []
        for review in review_elements:
            try:
                title = self._get_safe_text(review, Reviews.TITLE)
                raw_score = self._get_safe_text(review, Reviews.SCORE)
                score = extract_score_from_text(raw_score)
                
                pos = self._get_safe_text(review, Reviews.POSITIVE)
                neg = self._get_safe_text(review, Reviews.NEGATIVE)
                
                if not pos and not neg:
                    body = self._get_safe_text(review, Reviews.BODY_FALLBACK)
                    if body: pos = body

                date = self._get_safe_text(review, Reviews.DATE)

                data = {
                    "hotel_name": self.hotel_name, "hotel_url": self.hotel_url, 
                    "title": title, "score": score,
                    "positive": pos, "negative": neg, 
                    "date": date
                }
                
                if data not in page_reviews:
                    page_reviews.append(data)
            except StaleElementReferenceException:
                continue
        return page_reviews

    def next_page(self) -> bool:
        """Intenta ir a la siguiente página de reseñas."""
        try:
            # Obtener referencia al primer elemento actual para esperar que desaparezca (staleness)
            current_reviews = self.driver.find_elements(By.CSS_SELECTOR, Reviews.ITEM)
            first_review = current_reviews[0] if current_reviews else None

            next_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, Reviews.NEXT_PAGE))
            )
            self.driver.execute_script("arguments[0].click();", next_btn)
            
            if first_review:
                WebDriverWait(self.driver, 10).until(EC.staleness_of(first_review))
            
            # Esperar a que carguen los nuevos
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, Reviews.ITEM))
            )
            return True
        except (TimeoutException, NoSuchElementException):
            logging.info("      [END] Fin de la paginación.")
            return False
        except Exception as e:
            logging.error(f"Error al intentar cambiar de página: {e}")
            return False

import logging
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from src.booking_selectors import Reviews
from src.utils.cleaning import extract_score_from_text
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# Importar TypedDict desde pipeline (o moverlo a models/types si fuera mejor, pero por ahora aquí)
# Para evitar circular imports, definimos ReviewData aquí también o usamos Dict por ahora con comentario
# Lo ideal es tener un types.py, pero para no crear más archivos, lo definiremos aquí o usaremos Dict
# Dado que pipeline importa pages, pages no debería importar pipeline.
# Usaremos Dict con comentario de tipo o duplicaremos la definición simple.
from typing import TypedDict

class ReviewData(TypedDict):
    hotel_name: str
    hotel_url: str
    title: str
    score: str
    positive: str
    negative: str
    date: str

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

    def _extract_review_data(self, review_element) -> ReviewData:
        """
        Extrae datos de un elemento de reseña individual.
        """
        try:
            title = self._get_safe_text(review_element, Reviews.TITLE)
            raw_score = self._get_safe_text(review_element, Reviews.SCORE)
            score = extract_score_from_text(raw_score)
            
            pos = self._get_safe_text(review_element, Reviews.POSITIVE)
            neg = self._get_safe_text(review_element, Reviews.NEGATIVE)
            
            if not pos and not neg:
                body = self._get_safe_text(review_element, Reviews.BODY_FALLBACK)
                if body: pos = body

            date = self._get_safe_text(review_element, Reviews.DATE)

            return {
                "hotel_name": self.hotel_name, "hotel_url": self.hotel_url, 
                "title": title, "score": score,
                "positive": pos, "negative": neg, 
                "date": date
            }
        except StaleElementReferenceException:
            logging.warning("Stale element encountered while extracting review data.")
            return {} # type: ignore
        except Exception as e:
            logging.warning(f"Error extracting review data: {e}")
            return {} # type: ignore

    def extract_current_page(self) -> List[ReviewData]:
        """Extrae las reseñas visibles en la página actual del modal."""
        try:
            # Esperar presencia inicial
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, Reviews.ITEM))
            )
        except TimeoutException:
            logging.info("Tiempo de espera agotado buscando reseñas en esta página (posible fin).")
            return []

        # Obtener elementos y procesar iterando directamente
        review_elements = self.driver.find_elements(By.CSS_SELECTOR, Reviews.ITEM)
        page_reviews = []
        
        for i, element in enumerate(review_elements):
            data = self._extract_review_data(element)
            if data and data not in page_reviews:
                page_reviews.append(data)
                
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

    def extract_all_reviews(self, max_reviews: int = 1000) -> List[ReviewData]:
        """
        Extrae todas las reseñas disponibles paginando hasta alcanzar max_reviews.
        """
        all_reviews = []
        page = 1
        
        while True:
            logging.info(f"      [PAGE] Procesando página {page}...")
            batch = self.extract_current_page()
            
            if batch:
                all_reviews.extend(batch)
                logging.info(f"      [PAGE] Pág {page}: {len(batch)} reseñas extraídas. Total: {len(all_reviews)}")
            
            if len(all_reviews) >= max_reviews:
                logging.info(f"      [LIMIT] Límite de {max_reviews} reseñas alcanzado.")
                break
            
            if not self.next_page():
                break
                
            page += 1
            
        return all_reviews[:max_reviews]

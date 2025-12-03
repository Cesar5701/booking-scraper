import json
import logging
from typing import List, Dict, Generator
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    StaleElementReferenceException, ElementClickInterceptedException
)

from booking_selectors import HotelPage, Reviews
from utils.cleaning import extract_score_from_text

class ReviewExtractor:
    """
    Encapsula la lógica de extracción de reseñas de una página de hotel.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Inicializa el extractor con un driver de Selenium.
        
        Args:
            driver (webdriver.Chrome): Instancia del navegador controlada por Selenium.
        """
        self.driver = driver

    def _get_safe_text(self, element, selector: str) -> str:
        """
        Intenta extraer el texto de un elemento hijo usando un selector CSS.
        Retorna cadena vacía si no se encuentra.
        """
        try:
            return element.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return ""

    def get_hotel_name(self) -> str:
        """Obtiene el nombre del hotel usando múltiples estrategias."""
        driver = self.driver
        
        # ESTRATEGIA 1: JSON-LD
        try:
            scripts = driver.find_elements(*HotelPage.NAME_JSON_LD)
            for script in scripts:
                content = script.get_attribute("innerHTML")
                if "Hotel" in content or "LodgingBusiness" in content:
                    data = json.loads(content)
                    if isinstance(data, dict): data = [data]
                    for item in data:
                        if item.get("@type") in ["Hotel", "LodgingBusiness", "Resort", "Hostel"]:
                            name = item.get("name")
                            if name: return name
        except (NoSuchElementException, json.JSONDecodeError): 
            pass

        # ESTRATEGIA 2: OpenGraph
        try:
            og_title = driver.find_element(*HotelPage.NAME_OG_TITLE).get_attribute("content")
            if og_title: return og_title.split(",")[0].strip()
        except NoSuchElementException: 
            pass

        # ESTRATEGIA 3: ID
        try:
            id_name = driver.find_element(*HotelPage.NAME_ID).text.strip()
            if id_name: return id_name
        except NoSuchElementException: 
            pass

        # ESTRATEGIA 4: Visual Selectors
        for sel in HotelPage.NAME_VISUAL_SELECTORS:
            txt = self._get_safe_text(driver, sel)
            if txt: return txt

        # ESTRATEGIA 5: Title
        try:
            return driver.title.split("Booking.com")[0].replace("Updated Prices", "").strip().rstrip("-").strip()
        except Exception:
            return "Nombre_Desconocido"

    def get_total_review_count(self) -> int:
        """Obtiene el conteo total de reseñas esperado."""
        driver = self.driver
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, HotelPage.REVIEW_COUNT_LINKS)
            for elem in elements:
                text = elem.text
                import re
                match = re.search(r'\((\d+[\.,]?\d*)\)', text)
                if match:
                    num_str = match.group(1).replace('.', '').replace(',', '')
                    return int(num_str)
                    
            count_elem = driver.find_element(By.CSS_SELECTOR, HotelPage.REVIEW_COUNT_SIDEBAR)
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

    def extract_reviews(self, hotel_url: str) -> Generator[List[Dict], None, None]:
        """
        Navega a la URL del hotel, abre el panel de reseñas y extrae los datos paginados.
        
        Args:
            hotel_url (str): URL de la página del hotel en Booking.com.
            
        Yields:
            List[Dict]: Una lista de diccionarios, donde cada diccionario representa una reseña.
        """
        driver = self.driver
        driver.get(hotel_url)
        
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            logging.error(f"Timeout cargando la página del hotel: {hotel_url}")
            return

        hotel_name = self.get_hotel_name()
        logging.info(f"   [HOTEL] Procesando: {hotel_name}")
        
        expected_count = self.get_total_review_count()
        if expected_count > 0:
            logging.info(f"      [INFO] Se esperan aprox. {expected_count} reseñas.")

        # Cerrar popups
        try:
            WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, HotelPage.LOGIN_POPUP_CLOSE))
            ).click()
        except (TimeoutException, NoSuchElementException): pass

        # Abrir pestaña reseñas
        logging.info("      -> Intentando abrir panel de reseñas...")
        reviews_opened = False
        for by, selector in HotelPage.OPEN_REVIEWS_STRATEGIES:
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
            logging.warning(f"No se pudo abrir la pestaña de reseñas para: {hotel_url}")
            return

        # Paginación
        page = 1
        total_extracted = 0
        
        while True:
            try:
                review_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, Reviews.ITEM))
                )
            except TimeoutException:
                logging.info("Tiempo de espera agotado buscando reseñas en esta página (posible fin).")
                break

            logging.info(f"      [PAGE] Pág {page}: Encontrados {len(review_elements)} elementos.")
            
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
                        "hotel_name": hotel_name, "hotel_url": hotel_url, 
                        "title": title, "score": score,
                        "positive": pos, "negative": neg, 
                        "date": date
                    }
                    
                    if data not in page_reviews:
                        page_reviews.append(data)
                except StaleElementReferenceException:
                    continue 
            
            if page_reviews:
                total_extracted += len(page_reviews)
                yield page_reviews

            # Siguiente página
            try:
                next_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, Reviews.NEXT_PAGE))
                )
                
                current_first_review = review_elements[0] if review_elements else None
                driver.execute_script("arguments[0].click();", next_btn)
                
                if current_first_review:
                    WebDriverWait(driver, 10).until(EC.staleness_of(current_first_review))
                
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, Reviews.ITEM))
                )
                page += 1
            except (TimeoutException, NoSuchElementException):
                logging.info("      [END] Fin de la paginación.")
                break 
            except Exception as e:
                logging.error(f"Error al intentar cambiar de página: {e}")
                break

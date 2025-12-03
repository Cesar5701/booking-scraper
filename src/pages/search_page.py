import logging
import csv
from typing import List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import config
from booking_selectors import SearchResults

class SearchPage:
    """
    Page Object para la página de resultados de búsqueda.
    """
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def load_results(self, url: str) -> bool:
        """Navega a la URL y espera a que carguen los resultados."""
        logging.info(f"Navegando a: {url}")
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, config.MAX_WAIT_TIME).until(
                EC.presence_of_element_located(SearchResults.PROPERTY_CARD)
            )
            return True
        except TimeoutException:
            logging.error("Los resultados iniciales no cargaron. Abortando.")
            return False

    def scroll_and_load_all(self):
        """Maneja el scroll infinito y el botón 'Cargar más'."""
        logging.info("Cargando lista completa (Scroll + Botón 'Cargar más')...")
        scroll_attempts = 0
        max_attempts = 3
        
        while scroll_attempts < max_attempts:
            current_cards = len(self.driver.find_elements(*SearchResults.PROPERTY_CARD))
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            try:
                load_more_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(SearchResults.LOAD_MORE_BUTTON)
                )
                self.driver.execute_script("arguments[0].click();", load_more_btn)
                logging.info("   -> Botón 'Cargar más' clickeado.")
                
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(*SearchResults.PROPERTY_CARD)) > current_cards
                )
                scroll_attempts = 0
            except TimeoutException:
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                new_cards = len(self.driver.find_elements(*SearchResults.PROPERTY_CARD))
                
                if new_height == last_height and new_cards == current_cards:
                    scroll_attempts += 1
                    logging.info(f"   [WAIT] No se detectaron cambios. Intento {scroll_attempts}/{max_attempts}")
                else:
                    scroll_attempts = 0

    def get_hotel_links(self) -> List[str]:
        """Extrae los enlaces de los hoteles encontrados."""
        logging.info("Extrayendo enlaces finales...")
        elements = self.driver.find_elements(By.CSS_SELECTOR, SearchResults.HOTEL_LINKS)
        links = list(dict.fromkeys([e.get_attribute("href") for e in elements if e.get_attribute("href")]))
        logging.info(f"TOTAL HOTELES ENCONTRADOS: {len(links)}")
        return links

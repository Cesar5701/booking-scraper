import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from src.booking_selectors import HotelPage as HotelPageSelectors

class HotelInfoExtractor:
    """
    Clase auxiliar para extraer información estática del hotel (nombre, etc.)
    separando esta lógica del Page Object principal.
    """
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def get_name(self) -> str:
        """Obtiene el nombre del hotel usando múltiples estrategias."""
        driver = self.driver
        
        # ESTRATEGIA 1: JSON-LD
        try:
            scripts = driver.find_elements(*HotelPageSelectors.NAME_JSON_LD)
            for script in scripts:
                content = script.get_attribute("innerHTML")
                if "Hotel" in content or "LodgingBusiness" in content:
                    data = json.loads(content)
                    if isinstance(data, dict): data = [data]
                    for item in data:
                        if item.get("@type") in ["Hotel", "LodgingBusiness", "Resort", "Hostel"]:
                            name = item.get("name")
                            if name: return name
        except (NoSuchElementException, json.JSONDecodeError): pass

        # ESTRATEGIA 2: OpenGraph
        try:
            og_title = driver.find_element(*HotelPageSelectors.NAME_OG_TITLE).get_attribute("content")
            if og_title: return og_title.split(",")[0].strip()
        except NoSuchElementException: pass

        # ESTRATEGIA 3: ID
        try:
            id_name = driver.find_element(*HotelPageSelectors.NAME_ID).text.strip()
            if id_name: return id_name
        except NoSuchElementException: pass

        # ESTRATEGIA 4: Visual Selectors
        for sel in HotelPageSelectors.NAME_VISUAL_SELECTORS:
            try:
                txt = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                if txt: return txt
            except NoSuchElementException: continue

        # ESTRATEGIA 5: Title
        try:
            return driver.title.split("Booking.com")[0].replace("Updated Prices", "").strip().rstrip("-").strip()
        except Exception:
            return "Nombre_Desconocido"

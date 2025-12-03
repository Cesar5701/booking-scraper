import csv
import time
import os
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import List

import config
from core.driver import initialize_driver
from core.database import engine, Base
from core.pipeline import run_pipeline
from booking_selectors import SearchResults

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# --- CONFIGURACIÓN DEL SCRAPER ---
# Usamos 'lang=es' para asegurar que la interfaz cargue en español
# Variables importadas de config.py

def get_all_hotel_links(driver: webdriver.Chrome, url: str) -> List[str]:
    """
    Fase 1: Obtener enlaces de todos los hoteles en la búsqueda.
    
    Args:
        driver: Instancia de Selenium WebDriver.
        url: URL de búsqueda de Booking.
        
    Returns:
        List[str]: Lista de URLs de los hoteles encontrados.
    """
    logging.info(f"Navegando a: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, config.MAX_WAIT_TIME).until(
            EC.presence_of_element_located(SearchResults.PROPERTY_CARD)
        )
    except TimeoutException:
        logging.error("Los resultados iniciales no cargaron. Abortando.")
        return []

    logging.info("Cargando lista completa (Scroll + Botón 'Cargar más')...")
    scroll_attempts = 0
    max_attempts = 3
    
    while scroll_attempts < max_attempts:
        # Guardar número actual de elementos para comparar
        current_cards = len(driver.find_elements(*SearchResults.PROPERTY_CARD))
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        try:
            # Esperar a que aparezca el botón o que cambie la altura/elementos
            # Selector bilingüe para el botón de cargar más
            load_more_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(SearchResults.LOAD_MORE_BUTTON)
            )
            driver.execute_script("arguments[0].click();", load_more_btn)
            logging.info("   -> Botón 'Cargar más' clickeado.")
            
            # Esperar a que carguen más elementos (CRÍTICO: esperar cambio en conteo)
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(*SearchResults.PROPERTY_CARD)) > current_cards
            )
            scroll_attempts = 0
        except TimeoutException:
            # Si no aparece botón, tal vez solo es scroll infinito o ya no hay más
            new_height = driver.execute_script("return document.body.scrollHeight")
            # Verificamos si la altura cambió O si hay más elementos
            new_cards = len(driver.find_elements(*SearchResults.PROPERTY_CARD))
            
            if new_height == last_height and new_cards == current_cards:
                scroll_attempts += 1
                logging.info(f"   [WAIT] No se detectaron cambios. Intento {scroll_attempts}/{max_attempts}")
            else:
                scroll_attempts = 0 # Se movió, seguimos intentando
    
    logging.info("Extrayendo enlaces finales...")
    # Intentar múltiples selectores para los enlaces
    elements = driver.find_elements(By.CSS_SELECTOR, SearchResults.HOTEL_LINKS)
    links = list(dict.fromkeys([e.get_attribute("href") for e in elements if e.get_attribute("href")]))
    
    logging.info(f"TOTAL HOTELES ENCONTRADOS: {len(links)}")
    
    # Guardar respaldo de enlaces
    with open(config.LINKS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hotel_link"])
        for l in links: writer.writerow([l])
        
    return links

def main():
    # Configurar Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler()
        ]
    )

    # Lógica de Reanudación
    processed_urls = set()
    if os.path.isfile(config.RAW_REVIEWS_FILE):
        try:
            df = pd.read_csv(config.RAW_REVIEWS_FILE)
            processed_urls = set(df['hotel_url'].unique())
            logging.info(f"[RESUME] Lógica de reanudación activada. {len(processed_urls)} hoteles ya procesados.")
        except (pd.errors.EmptyDataError, KeyError):
             logging.warning(f"[WARN] Archivo de reseñas vacío o inválido. Iniciando desde cero.")
             pass

    # Fase 1: Obtener Links (Secuencial, un solo driver)
    logging.info("--- FASE 1: BÚSQUEDA DE HOTELES ---")
    driver = initialize_driver()
    try:
        links = get_all_hotel_links(driver, config.SEARCH_URL)
    finally:
        driver.quit()
        
    if not links:
        logging.error("[ERROR] No se encontraron hoteles.")
        return

    # Filtrar ya procesados
    links_to_process = [l for l in links if l not in processed_urls]
    
    if config.HOTEL_VISIT_LIMIT > 0:
        logging.info(f"[TEST MODE] Procesando solo los primeros {config.HOTEL_VISIT_LIMIT} hoteles.")
        links_to_process = links_to_process[:config.HOTEL_VISIT_LIMIT]
    else:
        logging.info(f"[FULL MODE] Procesando {len(links_to_process)} hoteles pendientes.")

    if not links_to_process:
        logging.info("[INFO] No hay hoteles nuevos para procesar.")
        return

    # Fase 2: Procesamiento Paralelo (Delegado al Pipeline)
    run_pipeline(links_to_process)

if __name__ == "__main__":
    main()
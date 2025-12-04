import csv
import logging
import os
from typing import List

import pandas as pd
from selenium import webdriver

from src import config
from src.core.database import engine, Base
from src.core.driver import initialize_driver
from src.core.pipeline import run_pipeline
from src.pages.search_page import SearchPage
from src.utils.logging_config import setup_logging

# Crear tablas si no existen


# --- CONFIGURACIÓN DEL SCRAPER ---
# Usamos 'lang=es' para asegurar que la interfaz cargue en español
# Variables importadas de config.py

def get_all_hotel_links(driver: webdriver.Chrome, url: str) -> List[str]:
    """
    Fase 1: Obtener enlaces de todos los hoteles en la búsqueda usando POM.
    """
    search_page = SearchPage(driver)
    
    if not search_page.load_results(url):
        return []

    search_page.scroll_and_load_all()
    return search_page.get_hotel_links()



def main():
    # Configurar Logging
    setup_logging()

    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)

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

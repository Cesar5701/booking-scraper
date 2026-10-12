"""
Módulo Principal de Extracción (Scraping)

Punto de entrada para el sistema de extracción de reseñas de Booking.com.
Coordina dos fases principales:
1. Descubrimiento (Fase 1): Usa Selenium para navegar por los resultados de búsqueda y extraer todos los URLs de los hoteles.
2. Extracción Paralela (Fase 2): Delega la lista de URLs al pipeline multihilo para la extracción mediante peticiones a la API interna.
"""
import csv
import logging
import os
import time
from typing import List

import pandas as pd
from selenium import webdriver

from src import config
from src.core.database import engine, Base
from src.core.driver import initialize_driver
from src.core.pipeline import run_pipeline
from src.pages.search_page import SearchPage
from src.utils.logging_config import setup_logging

def get_all_hotel_links(driver: webdriver.Chrome, url: str) -> List[str]:
    """
    Fase 1: Obtener enlaces de todos los hoteles en la búsqueda usando el patrón Page Object Model (POM).
    Esta fase es secuencial y utiliza Selenium, ya que la página de búsqueda principal
    requiere renderizado de JavaScript para cargar todos los listados al hacer scroll.
    
    Args:
        driver (webdriver.Chrome): Instancia del navegador automatizado.
        url (str): URL de búsqueda inicial de Booking.
        
    Returns:
        List[str]: Lista de URLs absolutas de los hoteles encontrados.
    """
    search_page = SearchPage(driver)
    
    # Cargar la página inicial
    if not search_page.load_results(url):
        return []

    # Realizar scroll dinámico para cargar resultados asíncronos (lazy loading)
    search_page.scroll_and_load_all()
    # Extraer las URLs del DOM renderizado
    return search_page.get_hotel_links()



def main():
    """
    Función principal de orquestación. Resuelve el estado de la base de datos, 
    gestiona la lógica de reanudación (resume) en caso de interrupciones previas,
    y dispara las dos fases del scraping.
    """
    # Configurar formato y nivel de Logging
    setup_logging()

    # Inicializar Base de Datos Relacional. 
    # Crea las tablas (como 'reviews') si no existen en SQLite.
    Base.metadata.create_all(bind=engine)

    # --- Lógica de Reanudación Automática (Recovery) ---
    # Lee el CSV de respaldo para identificar qué hoteles ya han sido scrapeados completamente
    # y evitar procesarlos de nuevo, ahorrando tiempo y peticiones.
    processed_urls = set()
    if os.path.isfile(config.RAW_REVIEWS_FILE):
        try:
            df = pd.read_csv(config.RAW_REVIEWS_FILE)
            processed_urls = set(df['hotel_url'].unique())
            logging.info(f"[RESUME] Lógica de reanudación activada. {len(processed_urls)} hoteles ya procesados.")
        except (pd.errors.EmptyDataError, KeyError):
             logging.warning(f"[WARN] Archivo de reseñas vacío o inválido. Iniciando desde cero.")
             pass

    # --- Fase 1: Obtener Links (Descubrimiento Secuencial) ---
    logging.info("--- FASE 1: BÚSQUEDA DE HOTELES ---")
    start_phase1 = time.time()
    driver = initialize_driver()
    try:
        # Se obtiene el listado general manipulando el DOM visual
        links = get_all_hotel_links(driver, config.SEARCH_URL)
    finally:
        # Importante: Siempre cerrar el driver para liberar recursos del SO
        driver.quit()
        
    logging.info(f"[TIMING] Fase 1 completada en {time.time() - start_phase1:.2f}s")
    
    if not links:
        logging.error("[ERROR] No se encontraron hoteles.")
        return

    # --- Filtrado de Tareas Pendientes ---
    # Intersecar la lista obtenida contra el registro de completados
    links_to_process = [l for l in links if l not in processed_urls]
    
    # Modo de prueba/desarrollo: Limita la cantidad de hoteles a extraer según config.py
    if config.HOTEL_VISIT_LIMIT > 0:
        logging.info(f"[TEST MODE] Procesando solo los primeros {config.HOTEL_VISIT_LIMIT} hoteles.")
        links_to_process = links_to_process[:config.HOTEL_VISIT_LIMIT]
    else:
        logging.info(f"[FULL MODE] Procesando {len(links_to_process)} hoteles pendientes.")

    if not links_to_process:
        logging.info("[INFO] No hay hoteles nuevos para procesar.")
        return

    # --- Fase 2: Procesamiento Paralelo por Arquitectura de Hilos ---
    # Delega el resto del trabajo pesado (Extracción REST API y Parseo BeautifulSoup)
    # al módulo pipeline.py para escalar el rendimiento en paralelo sin Selenium.
    start_phase2 = time.time()
    run_pipeline(links_to_process)
    logging.info(f"[TIMING] Fase 2 completada en {time.time() - start_phase2:.2f}s")


if __name__ == "__main__":
    main()

import csv
import time
import os
import random
import json
import logging
import traceback
import queue
import threading
import concurrent.futures
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from typing import List, Dict, Generator, Optional
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import hashlib
from sqlalchemy.exc import IntegrityError

import config
from core.driver import initialize_driver
from core.database import SessionLocal, engine, Base
from models import Review

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# --- CONFIGURACIÓN DEL SCRAPER ---
# Usamos 'lang=es' para asegurar que la interfaz cargue en español
# Variables importadas de config.py


# initialize_driver se importa desde core.driver


def csv_writer_listener(result_queue: queue.Queue, filename: str):
    """
    Hilo dedicado a escuchar la cola y escribir en el CSV.
    Termina cuando recibe None.
    """
    review_headers = ["hotel_name", "hotel_url", "title", "score", "positive", "negative", "date"]
    file_exists = os.path.isfile(filename)
    
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_headers)
        if not file_exists:
            writer.writeheader()
            
        while True:
            batch = result_queue.get()
            if batch is None: # Poison pill
                break
            
            try:
                # 1. Escribir en CSV
                writer.writerows(batch)
                f.flush()
                
                # 2. Escribir en DB
                db = SessionLocal()
                saved_count = 0
                try:
                    for item in batch:
                        # Generar Hash Único
                        # Usamos hotel_url + date + title + positive + negative para identificar unicidad
                        unique_str = f"{item.get('hotel_url')}{item.get('date')}{item.get('title')}{item.get('positive')}{item.get('negative')}"
                        review_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
                        
                        review = Review(
                            hotel_name=item.get("hotel_name"),
                            hotel_url=item.get("hotel_url"),
                            title=item.get("title"),
                            score=item.get("score"),
                            positive=item.get("positive"),
                            negative=item.get("negative"),
                            date=item.get("date"),
                            review_hash=review_hash
                        )
                        try:
                            db.add(review)
                            db.commit()
                            saved_count += 1
                        except IntegrityError:
                            db.rollback()
                            # Duplicado detectado, lo ignoramos silenciosamente
                            pass
                            
                except Exception as db_e:
                    logging.error(f"Error guardando en DB: {db_e}")
                    db.rollback()
                finally:
                    db.close()

                logging.info(f"   [SAVED] {len(batch)} reseñas procesadas ({saved_count} nuevas en DB).")
            except Exception as e:
                logging.error(f"Error escribiendo datos: {e}")
            finally:
                result_queue.task_done()


def worker_process(urls: List[str], result_queue: queue.Queue, worker_id: int):
    """
    Proceso de trabajador que maneja su propio driver y procesa una lista de URLs.
    """
    logging.info(f"[WORKER] Worker {worker_id}: Iniciando con {len(urls)} hoteles.")
    driver = initialize_driver()
    
    processed_count = 0
    try:
        for url in urls:
            logging.info(f"[WORKER] Worker {worker_id}: Procesando {url}")
            try:
                for batch in extract_reviews_from_hotel(driver, url):
                    if batch:
                        result_queue.put(batch)
            except Exception as e:
                logging.error(f"Worker {worker_id} error en {url}: {e}", exc_info=True)
            processed_count += 1
            
    finally:
        logging.info(f"[WORKER] Worker {worker_id}: Finalizando. Procesados: {processed_count}")
        driver.quit()


def get_all_hotel_links(driver: webdriver.Chrome, url: str) -> List[str]:
    """
    Fase 1: Obtener enlaces de todos los hoteles en la búsqueda.
    
    Args:
        driver: Instancia de Selenium WebDriver.
        url: URL de búsqueda de Booking.
        
    Returns:
        List[str]: Lista de URLs de los hoteles encontrados.
    """
    print(f"[INFO] Navegando a: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, config.MAX_WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="property-card"]'))
        )
    except TimeoutException:
        print("[ERROR] Los resultados iniciales no cargaron. Abortando.")
        return []

    print("[INFO] Cargando lista completa (Scroll + Botón 'Cargar más')...")
    scroll_attempts = 0
    max_attempts = 3
    
    while scroll_attempts < max_attempts:
        # Guardar número actual de elementos para comparar
        current_cards = len(driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]'))
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        try:
            # Esperar a que aparezca el botón o que cambie la altura/elementos
            # Selector bilingüe para el botón de cargar más
            load_more_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Load more') or contains(., 'Cargar más')]"))
            )
            driver.execute_script("arguments[0].click();", load_more_btn)
            print("   -> Botón 'Cargar más' clickeado.")
            
            # Esperar a que carguen más elementos (CRÍTICO: esperar cambio en conteo)
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')) > current_cards
            )
            scroll_attempts = 0
        except TimeoutException:
            # Si no aparece botón, tal vez solo es scroll infinito o ya no hay más
            new_height = driver.execute_script("return document.body.scrollHeight")
            # Verificamos si la altura cambió O si hay más elementos
            new_cards = len(driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]'))
            
            if new_height == last_height and new_cards == current_cards:
                scroll_attempts += 1
                logging.info(f"   [WAIT] No se detectaron cambios. Intento {scroll_attempts}/{max_attempts}")
            else:
                scroll_attempts = 0 # Se movió, seguimos intentando
    
    print("\n[INFO] Extrayendo enlaces finales...")
    # Intentar múltiples selectores para los enlaces
    elements = driver.find_elements(By.CSS_SELECTOR, 'a.e3859ef1a4, a[data-testid="title-link"], a[data-testid="property-card-desktop-single-image"], .c-property-card__title a')
    links = list(dict.fromkeys([e.get_attribute("href") for e in elements if e.get_attribute("href")]))
    
    print(f"[INFO] TOTAL HOTELES ENCONTRADOS: {len(links)}")
    
    # Guardar respaldo de enlaces
    # Guardar respaldo de enlaces
    with open(config.LINKS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hotel_link"])
        for l in links: writer.writerow([l])
        
    return links


def _get_safe_text(element, selector: str) -> str:
    """
    Ayuda a extraer texto de forma segura sin romper el script.
    
    Args:
        element: WebElement padre.
        selector: Selector CSS a buscar dentro del elemento.
        
    Returns:
        str: Texto encontrado o cadena vacía.
    """
    try:
        return element.find_element(By.CSS_SELECTOR, selector).text.strip()
    except NoSuchElementException:
        return ""


def get_hotel_name_robust(driver: webdriver.Chrome) -> str:
    """
    Intenta extraer el nombre del hotel usando JSON-LD (metadatos ocultos)
    como prioridad, ya que los selectores CSS cambian constantemente.
    
    Args:
        driver: Instancia de Selenium WebDriver.
        
    Returns:
        str: Nombre del hotel encontrado o 'Nombre_Desconocido'.
    """
    # ESTRATEGIA 1: JSON-LD (Datos Estructurados - Muy Estable)
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            content = script.get_attribute("innerHTML")
            if "Hotel" in content or "LodgingBusiness" in content:
                data = json.loads(content)
                if isinstance(data, dict): data = [data]
                for item in data:
                    if item.get("@type") in ["Hotel", "LodgingBusiness", "Resort", "Hostel"]:
                        name = item.get("name")
                        if name: return name
    except Exception: 
        pass # JSON-LD es opcional, no es crítico loguear error aquí

    # ESTRATEGIA 2: Meta Tags OpenGraph
    try:
        og_title = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:title"]').get_attribute("content")
        if og_title: return og_title.split(",")[0].strip()
    except Exception: 
        pass

    # ESTRATEGIA 3: ID Clásico
    try:
        id_name = driver.find_element(By.ID, "hp_hotel_name").text.strip()
        if id_name: return id_name
    except Exception: 
        pass

    # ESTRATEGIA 4: Selectores Visuales (Fallback)
    visual_selectors = ['h2.pp-header__title', 'h2[data-testid="post-booking-header-title"]', '.hp__hotel-name']
    for sel in visual_selectors:
        txt = _get_safe_text(driver, sel)
        if txt: return txt

    # ESTRATEGIA 5: Título de la Pestaña
    try:
        return driver.title.split("Booking.com")[0].replace("Updated Prices", "").strip().rstrip("-").strip()
    except Exception:
        return "Nombre_Desconocido"


def get_total_review_count(driver: webdriver.Chrome) -> int:
    """
    Intenta obtener el número total de reseñas desde la pestaña o encabezado.
    """
    try:
        # Busca elementos que contengan números entre paréntesis, típico de Booking
        # Ej: "Comentarios (123)" o "Guest reviews (123)"
        elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="review-score-link"], .js-review-tab-link, [data-tab-target="htReviews"]')
        
        for elem in elements:
            text = elem.text
            # Extraer número entre paréntesis
            import re
            match = re.search(r'\((\d+[\.,]?\d*)\)', text)
            if match:
                num_str = match.group(1).replace('.', '').replace(',', '')
                return int(num_str)
                
        # Fallback: Buscar en el sidebar o header de reviews
        count_elem = driver.find_element(By.CSS_SELECTOR, '.bui-review-score__text, .d8eab2cf7f')
        if count_elem:
             text = count_elem.text
             import re
             match = re.search(r'(\d+[\.,]?\d*)', text)
             if match:
                num_str = match.group(1).replace('.', '').replace(',', '')
                return int(num_str)

    except Exception:
        pass
    
    return 0


def extract_reviews_from_hotel(driver: webdriver.Chrome, hotel_url: str) -> Generator[List[Dict], None, None]:
    """
    Fase 2: Entrar al hotel, obtener nombre, abrir reseñas y paginar.
    GENERADOR: Yields lotes de reseñas por página.
    
    Args:
        driver: Instancia de Selenium WebDriver.
        hotel_url: URL del hotel a procesar.
        
    Yields:
        List[Dict]: Lista de reseñas extraídas de la página actual.
    """
    driver.get(hotel_url)
    
    # Esperar a que cargue el cuerpo de la página o el título
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        logging.error(f"Timeout cargando la página del hotel: {hotel_url}")
        return

    # 1. Obtener nombre robusto
    hotel_name = get_hotel_name_robust(driver)
    print(f"   [HOTEL] Procesando: {hotel_name}")
    
    # 1.5 Obtener conteo esperado (antes de abrir pestaña si es posible, o después)
    expected_count = get_total_review_count(driver)
    if expected_count > 0:
        print(f"      [INFO] Se esperan aprox. {expected_count} reseñas.")

    # 2. Intentar cerrar popups de login/cookies
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label*="Dismiss"], button[aria-label*="Ignorar"], button[aria-label*="Cerrar"]'))
        ).click()
    except Exception: pass

    # 3. ABRIR PESTAÑA DE RESEÑAS
    print("      -> Intentando abrir panel de reseñas...")
    reviews_opened = False
    
    # Lista de estrategias para abrir el panel
    # Lista de estrategias para abrir el panel
    open_strategies = [
        (By.CSS_SELECTOR, '[data-testid="review-score-link"]'),
        (By.CSS_SELECTOR, '[data-testid="review-score-component"]'),
        (By.CSS_SELECTOR, '.js-review-tab-link'),
        (By.CSS_SELECTOR, '[data-tab-target="htReviews"]'),
        (By.ID, "show_reviews_tab"),
        (By.CSS_SELECTOR, '[data-testid="guest-reviews-tab-trigger"]'),
        (By.PARTIAL_LINK_TEXT, "Comentarios"),
        (By.PARTIAL_LINK_TEXT, "Reviews"),
        (By.XPATH, "//a[contains(@href, '#tab-reviews')]")
    ]
    
    for by, selector in open_strategies:
        try:
            elem = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].click();", elem)
            # Esperar a que aparezca AL MENOS UNA reseña o el contenedor de lista
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="review"], .c-review-block, .review_list_new_item_block'))
            )
            reviews_opened = True
            print(f"      [OK] Panel abierto usando: {selector}")
            break
        except Exception:
            continue

    if not reviews_opened:
        logging.warning(f"No se pudo abrir la pestaña de reseñas para: {hotel_url}")
        return

    # 4. EXTRACCIÓN Y PAGINACIÓN
    # collected_reviews = [] # YA NO ACUMULAMOS TODO
    page = 1
    total_extracted = 0
    
    while True:
        # Esperar carga de reseñas en la página actual
        try:
            # Aumentado timeout a 10s
            review_elements = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="review"], li.review_item, .c-review-block'))
            )
        except TimeoutException:
            logging.info("Tiempo de espera agotado buscando reseñas en esta página (posible fin).")
            break

        print(f"      [PAGE] Pág {page}: Encontrados {len(review_elements)} elementos.")
        
        page_reviews = [] # Acumulamos solo la página actual
        
        for review in review_elements:
            try:
                # Extracción con selectores múltiples (fallback)
                title = _get_safe_text(review, '[data-testid="review-title"], .c-review-block__title')
                
                # Score
                raw_score = _get_safe_text(review, '[data-testid="review-score"], .bui-review-score__badge')

                # Limpiar el score: tomar solo la primera línea y reemplazar comas.
                if '\n' in raw_score:
                    score = raw_score.split('\n')[0]
                else:
                    score = raw_score
                
                score = score.replace("Score:", "").replace("Puntuación:", "").replace(",", ".").strip()
                
                # Texto Positivo/Negativo
                pos = _get_safe_text(review, '[data-testid="review-positive-text"], .c-review__body--positive')
                neg = _get_safe_text(review, '[data-testid="review-negative-text"], .c-review__body--negative')
                
                # Si no hay pos/neg separados, intentar buscar cuerpo general (raro en Booking, pero posible)
                if not pos and not neg:
                    body = _get_safe_text(review, '.c-review-block__row')
                    if body: pos = body # Guardamos en pos temporalmente

                # Fecha
                date = _get_safe_text(review, '[data-testid="review-date"], .c-review-block__date')

                data = {
                    "hotel_name": hotel_name, "hotel_url": hotel_url, 
                    "title": title, "score": score,
                    "positive": pos, "negative": neg, 
                    "date": date
                }
                
                # Evitar duplicados exactos en la misma página (raro pero posible)
                if data not in page_reviews:
                    page_reviews.append(data)
            except StaleElementReferenceException:
                continue 
        
        # YIELD DE LA PÁGINA ACTUAL
        if page_reviews:
            total_extracted += len(page_reviews)
            yield page_reviews

        # 5. IR A SIGUIENTE PÁGINA
        try:
            # Selector robusto para el botón "Siguiente"
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="pagination-next-link"], button[aria-label="Next page"], button[aria-label="Página siguiente"]'))
            )
            
            # Capturar el primer elemento de reseña actual para detectar cuando cambie la página (stale)
            current_first_review = review_elements[0] if review_elements else None
            
            driver.execute_script("arguments[0].click();", next_btn)
            
            # Esperar a que la lista de reseñas se actualice (stale element reference es buena señal de recarga)
            if current_first_review:
                WebDriverWait(driver, 10).until(
                    EC.staleness_of(current_first_review)
                )
            
            # Esperar a que aparezcan las nuevas reseñas
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="review"], li.review_item, .c-review-block'))
            )
            
            page += 1
        except (TimeoutException, NoSuchElementException):
            print("      [END] Fin de la paginación (no se detectó botón 'Siguiente' o no cargó siguiente página).")
            break 
        except Exception as e:
            logging.error(f"Error al intentar cambiar de página: {e}")
            break
            
    # Verificación final
    if expected_count > 0:
        if total_extracted < expected_count * 0.8: # Si falta más del 20%
             logging.warning(f"[WARN] {hotel_name}: Se esperaban {expected_count} reseñas, pero solo se extrajeron {total_extracted}.")
        else:
             print(f"      [DONE] Extracción completa: {total_extracted}/{expected_count}")


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

    # Fase 2: Procesamiento Paralelo
    logging.info(f"--- FASE 2: EXTRACCIÓN PARALELA ({config.MAX_WORKERS} Workers) ---")
    
    # Cola de resultados
    result_queue = queue.Queue()
    
    # Iniciar Hilo Escritor
    writer_thread = threading.Thread(target=csv_writer_listener, args=(result_queue, config.RAW_REVIEWS_FILE))
    writer_thread.start()
    
    # Dividir trabajo
    chunk_size = math.ceil(len(links_to_process) / config.MAX_WORKERS)
    chunks = [links_to_process[i:i + chunk_size] for i in range(0, len(links_to_process), chunk_size)]
    
    # Iniciar Workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = []
        for i, chunk in enumerate(chunks):
            futures.append(executor.submit(worker_process, chunk, result_queue, i+1))
        
        # Esperar a que terminen los workers
        concurrent.futures.wait(futures)
    
    # Detener Hilo Escritor
    result_queue.put(None)
    writer_thread.join()

    logging.info("\n[DONE] Proceso finalizado.")

if __name__ == "__main__":
    import math # Importar aquí o arriba
    main()
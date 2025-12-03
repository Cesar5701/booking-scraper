import queue
import threading
import concurrent.futures
import csv
import os
import logging
import hashlib
from typing import List
from sqlalchemy.exc import IntegrityError

import config
from core.driver import initialize_driver
from core.database import SessionLocal
from models import Review
from pages.hotel_page import HotelPage

def csv_writer_listener(result_queue: queue.Queue, filename: str):
    """
    Hilo dedicado a escuchar la cola y escribir en el CSV y DB.
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

def worker_process(urls: List[str], result_queue: queue.Queue, worker_id: int) -> None:
    """
    Proceso de trabajador que maneja su propio driver y procesa una lista de URLs.
    
    Args:
        urls (List[str]): Lista de URLs asignadas a este worker.
        result_queue (queue.Queue): Cola compartida para enviar resultados.
        worker_id (int): Identificador numérico del worker para logging.
    """
    logging.info(f"[WORKER] Worker {worker_id}: Iniciando con {len(urls)} hoteles.")
    driver = initialize_driver()
    hotel_page = HotelPage(driver)
    
    processed_count = 0
    try:
        for url in urls:
            logging.info(f"[WORKER] Worker {worker_id}: Procesando {url}")
            try:
                hotel_page.navigate(url)
                hotel_name = hotel_page.get_name()
                logging.info(f"   [HOTEL] Procesando: {hotel_name}")
                
                reviews_modal = hotel_page.open_reviews_modal()
                if not reviews_modal:
                    continue
                    
                page = 1
                while True:
                    batch = reviews_modal.extract_current_page()
                    if batch:
                        logging.info(f"      [PAGE] Pág {page}: Encontrados {len(batch)} elementos.")
                        result_queue.put(batch)
                    
                    if not reviews_modal.next_page():
                        break
                    page += 1
                    
            except Exception as e:
                logging.error(f"Worker {worker_id} error en {url}: {e}", exc_info=True)
            processed_count += 1
            
    finally:
        logging.info(f"[WORKER] Worker {worker_id}: Finalizando. Procesados: {processed_count}")
        driver.quit()

def run_pipeline(links_to_process: List[str]) -> None:
    """
    Orquesta la ejecución paralela del scraping dividiendo el trabajo entre workers.
    
    Args:
        links_to_process (List[str]): Lista total de URLs de hoteles a procesar.
    """
    import math
    
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

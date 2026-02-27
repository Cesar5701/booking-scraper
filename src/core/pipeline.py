import queue
import threading
import logging
import os
import csv
import hashlib
import time
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Optional, Set, TypedDict

from src import config
from src.core.database import SessionLocal
from src.models import Review
from src.pages.hotel_page import HotelPage
from src.core.driver import initialize_driver, get_driver_path
from src.utils.cleaning import fix_score_value

class ReviewData(TypedDict):
    hotel_name: str
    hotel_url: str
    title: str
    score: str
    positive: str
    negative: str
    date: str

def csv_writer_listener(result_queue: queue.Queue, filename: str) -> None:
    """
    Hilo dedicado a escuchar la cola de resultados y persistir los datos en CSV y Base de Datos.
    
    Implementa un patrón productor-consumidor donde este hilo actúa como consumidor único
    para escritura, evitando condiciones de carrera en el archivo y la DB.
    
    Args:
        result_queue (queue.Queue): Cola compartida de donde se leen los lotes de reseñas.
        filename (str): Ruta del archivo CSV donde se exportarán los datos.
    """
    review_headers = config.REVIEW_CSV_HEADERS
    file_exists = os.path.isfile(filename)
    
    # Abrimos el archivo en modo append, pero escribiremos solo lo que se guarde en DB
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_headers)
        if not file_exists:
            writer.writeheader()
            
        # Instanciar sesión de DB una vez para reutilizar conexión
        db = SessionLocal()
        try:
            while True:
                batch = result_queue.get()
                if batch is None: # Poison pill para detener el hilo
                    break
                
                try:
                    # 1. Intentar guardar en DB primero para filtrar duplicados
                    saved_count = 0
                    new_reviews_for_csv = []
                    start_db = time.time()

                    try:
                        for item in batch:
                            # 1.1 Eliminar Query Params cambiantes de la URL para el hash
                            # Ej: https://booking.com/hotel.html?aid=123 -> https://booking.com/hotel.html
                            raw_url = item.get('hotel_url', '')
                            clean_url = raw_url.split('?')[0]
                            # Actualizamos el diccionario con la URL limpia para cuando lo vayamos a escribir en CSV y BD
                            item['hotel_url'] = clean_url
                            
                            # 1.2 Generar Hash Único basado en campos clave
                            unique_str = f"{clean_url}{item.get('date')}{item.get('title')}{item.get('positive')}{item.get('negative')}"
                            review_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
                            
                            # Limpiar score antes de guardar
                            raw_score = item.get("score")
                            clean_score = fix_score_value(raw_score)

                            review = Review(
                                hotel_name=item.get("hotel_name"),
                                hotel_url=item.get("hotel_url"),
                                title=item.get("title"),
                                score=clean_score,
                                positive=item.get("positive"),
                                negative=item.get("negative"),
                                date=item.get("date"),
                                review_hash=review_hash,
                                room_type=item.get('room_type', ''),
                                traveler_type=item.get('traveler_type', ''),
                                nationality=item.get('nationality', ''),
                                nights_stayed=item.get('nights_stayed', '')
                            )
                            try:
                                db.add(review)
                                db.commit()
                                # Si llegamos aquí, se guardó correctamente (no era duplicado)
                                saved_count += 1
                                new_reviews_for_csv.append(item)
                            except IntegrityError:
                                db.rollback()
                                # Duplicado, lo ignoramos silenciosamente
                                pass
                                
                    except Exception as db_e:
                        logging.error(f"Error guardando en DB: {db_e}")
                        db.rollback()

                    # 2. Escribir en CSV solo los registros que fueron nuevos en la DB
                    db_time = time.time() - start_db
                    if new_reviews_for_csv:
                        writer.writerows(new_reviews_for_csv)
                        f.flush()

                    logging.info(f"   [SAVED] Procesados {len(batch)}. Nuevos en DB/CSV: {saved_count}. DB Time: {db_time:.4f}s")
                except Exception as e:
                    logging.error(f"Error escribiendo datos: {e}")
                finally:
                    result_queue.task_done()
        finally:
            db.close()

def worker_process(urls: List[str], result_queue: queue.Queue, worker_id: int) -> None:
    """
    Función ejecutada por cada hilo worker para procesar una lista de URLs de hoteles
    utilizando Requests directo hacia la API oculta de Booking.
    
    Args:
        urls (List[str]): Lista de URLs de hoteles asignada a este worker.
        result_queue (queue.Queue): Cola compartida para enviar los resultados (reseñas).
        worker_id (int): Identificador numérico del worker para logging.
    """
    total_urls = len(urls)
    logging.info(f"[HILO {worker_id}] Iniciado. Asignados {total_urls} hoteles API.")
    
    from src.pages.reviews_modal import ReviewsModal
    
    for idx, url in enumerate(urls, 1):
        start_url = time.time()
        try:
            # Extraer nombre
            try:
                hotel_name_from_url = url.split('/hotel/mx/')[1].split('.')[0]
            except Exception:
                hotel_name_from_url = url[:50] + "..."
                
            logging.info(f"[HILO {worker_id}] ({idx}/{total_urls}) Descargando API hotel: {hotel_name_from_url}")
            
            # Instanciar scraper de peticiones
            scraper = ReviewsModal(hotel_name=hotel_name_from_url, hotel_url=url)
            all_reviews = scraper.extract_all_reviews()
            
            if all_reviews:
                result_queue.put(all_reviews)
                logging.info(f"[HILO {worker_id}] -> {len(all_reviews)} reseñas extraidas de {hotel_name_from_url} y enviadas a DB.")
            else:
                logging.warning(f"[HILO {worker_id}] -> 0 reseñas encontradas para {hotel_name_from_url}.")
                
            logging.info(f"[TIMING - HILO {worker_id}] Tiempo total en {hotel_name_from_url}: {time.time() - start_url:.2f}s")
            
        except Exception as e:
            logging.error(f"[ERROR - HILO {worker_id}] Falló en {hotel_name_from_url}: {e}")
            continue
            
    logging.info(f"[HILO {worker_id}] Finalizó todas sus tareas correctamente.")

def run_pipeline(hotel_urls: List[str], processed_urls: Set[str] = set()) -> None:
    """
    Orquesta el proceso de scraping paralelo.
    
    Divide las URLs en chunks, inicia los workers y el hilo escritor, y espera a que terminen.
    
    Args:
        hotel_urls (List[str]): Lista total de URLs de hoteles a procesar.
        processed_urls (Set[str], optional): Conjunto de URLs ya procesadas para omitir.
    """
    # Filtrar URLs ya procesadas
    urls_to_process = [url for url in hotel_urls if url not in processed_urls]
    
    if not urls_to_process:
        logging.info("No hay nuevas URLs para procesar.")
        return

    logging.info(f"Iniciando pipeline para {len(urls_to_process)} hoteles con {config.MAX_WORKERS} workers.")

    # Cola para comunicar workers -> escritor
    result_queue = queue.Queue()
    
    # Iniciar hilo escritor (Consumer)
    writer_thread = threading.Thread(
        target=csv_writer_listener,
        args=(result_queue, config.RAW_REVIEWS_FILE)
    )
    writer_thread.start()
    
    # Dividir trabajo (URLs) entre workers
    chunk_size = (len(urls_to_process) // config.MAX_WORKERS) + 1
    chunks = [urls_to_process[i:i + chunk_size] for i in range(0, len(urls_to_process), chunk_size)]
    
    # Ya no ocupamos driver_path para BS4
    
    threads = []
    for i, chunk in enumerate(chunks):
        if not chunk: continue
        t = threading.Thread(target=worker_process, args=(chunk, result_queue, i+1))
        t.start()
        threads.append(t)
        
    # Esperar a que todos los workers terminen
    for t in threads:
        t.join()
        
    # Enviar señal de terminación (Poison Pill) al escritor
    result_queue.put(None)
    
    # Esperar a que el escritor termine
    writer_thread.join()
    
    logging.info("Pipeline finalizado correctamente.")

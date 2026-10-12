"""
Módulo de Arquitectura Multihilo (Pipeline)

Este módulo orquesta la Fase 2 del Scraping.
Implementa un patrón de concurrencia 'Productor-Consumidor':
- Múltiples hilos 'Worker' (Productores) realizan peticiones a las diferentes URLs en paralelo y colocan los datos en una cola.
- Un único hilo 'Writer' (Consumidor) lee secuencialmente de la cola y escribe en la base de datos (SQLite) y en un CSV, evitando bloqueos y carreras de escritura.
"""
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
    Hilo Consumidor dedicado a escuchar la cola de resultados y persistir los datos.
    
    Este hilo extrae lotes (batches) de diccionarios insertados por los workers.
    Para cada reseña:
    1. Unifica la URL para estabilizar la firma.
    2. Calcula un Hash MD5 criptográfico único para prevenir inserciones duplicadas.
    3. Intenta guardar la reseña en SQLite usando `db.add()`. 
       Si el Hash ya existe (Violación de Integridad), la base de datos lanza un IntegrityError y la reseña se descarta silenciosamente.
    4. Escribe la reseña de respaldo en el archivo CSV `RAW_REVIEWS_FILE` si y solo si la escritura a la base de datos fue exitosa.
    
    Args:
        result_queue (queue.Queue): Cola Thread-safe compartida.
        filename (str): Ruta del archivo CSV de respaldo.
    """
    review_headers = config.REVIEW_CSV_HEADERS
    file_exists = os.path.isfile(filename)
    
    # Abrimos el archivo CSV en modo append (agregar al final)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_headers)
        if not file_exists:
            writer.writeheader()
            
        # Instanciar sesión de base de datos relacional para el hilo consumidor
        db = SessionLocal()
        try:
            while True:
                # Espera bloqueante hasta que un Worker ponga un dato en la cola
                batch = result_queue.get()
                
                # Elemento nulo ("Poison Pill") usado para indicarle al hilo que todo el trabajo ha finalizado
                if batch is None: 
                    break
                
                try:
                    # 1. Proceso de Inserción y Filtrado de Duplicados en Base de Datos
                    saved_count = 0
                    new_reviews_for_csv = []
                    start_db = time.time()

                    try:
                        for item in batch:
                            # 1.1 Eliminar Query Params cambiantes de la URL para el hash
                            # Ej: https://booking.com/hotel.html?aid=123 -> https://booking.com/hotel.html
                            raw_url = item.get('hotel_url', '')
                            clean_url = raw_url.split('?')[0]
                            # Actualizamos el diccionario con la URL limpia
                            item['hotel_url'] = clean_url
                            
                            # 1.2 Generar Hash Único basado en los campos textuales clave. 
                            # Si Booking modifica el ID interno pero el texto es el mismo, el hash previene duplicidad.
                            unique_str = f"{clean_url}{item.get('date')}{item.get('title')}{item.get('positive')}{item.get('negative')}"
                            review_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
                            
                            # Limpiar score antes de guardar usando utilería
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
                                # Intenta insertar objeto ORM
                                db.add(review)
                                db.commit()
                                # Si el commit pasa, significa que el hash no existía en SQLite.
                                saved_count += 1
                                new_reviews_for_csv.append(item)
                            except IntegrityError:
                                # Hash duplicado encontrado, realizar rollback para liberar la transacción fallida
                                db.rollback()
                                pass
                                
                    except Exception as db_e:
                        logging.error(f"Error guardando en DB: {db_e}")
                        db.rollback()

                    # 2. Escribir en CSV solo los registros confirmados como nuevos
                    db_time = time.time() - start_db
                    if new_reviews_for_csv:
                        writer.writerows(new_reviews_for_csv)
                        f.flush()

                    logging.info(f"   [SAVED] Procesados {len(batch)}. Nuevos en DB/CSV: {saved_count}. DB Time: {db_time:.4f}s")
                except Exception as e:
                    logging.error(f"Error escribiendo datos: {e}")
                finally:
                    # Avisar a la cola que la tarea actual ha terminado
                    result_queue.task_done()
        finally:
            db.close()

def worker_process(urls: List[str], result_queue: queue.Queue, worker_id: int) -> None:
    """
    Función ejecutada por cada hilo Productor (Worker).
    
    El Worker toma una lista asignada (chunk) de URLs exclusivas para procesar.
    En lugar de levantar un driver completo de Selenium por hotel, llama al módulo `ReviewsModal`
    que realiza la extracción directamente sobre la API REST de Booking (vía HTTP Requests y BS4).
    
    Args:
        urls (List[str]): Lista de URLs de hoteles asignada a este worker por el coordinador.
        result_queue (queue.Queue): Cola compartida para depositar los lotes de extracción (resguardados por Thread-safety).
        worker_id (int): Identificador numérico del worker para seguimiento en Logs.
    """
    total_urls = len(urls)
    logging.info(f"[HILO {worker_id}] Iniciado. Asignados {total_urls} hoteles API.")
    
    from src.pages.reviews_modal import ReviewsModal
    
    for idx, url in enumerate(urls, 1):
        start_url = time.time()
        try:
            # Intentar extraer el ID / Nombre del Hotel directamente de la estructura web estandar de Booking .mx
            try:
                raw_name = url.split('/hotel/mx/')[1].split('.')[0]
                hotel_name_from_url = raw_name.replace('-', ' ').title()
            except Exception:
                hotel_name_from_url = url[:50] + "..."
                
            logging.info(f"[HILO {worker_id}] ({idx}/{total_urls}) Descargando API hotel: {hotel_name_from_url}")
            
            # 1. Instanciar la clase scraper Modal la cual utiliza Requests para omitir la carga general de scripts del Frontend
            scraper = ReviewsModal(hotel_name=hotel_name_from_url, hotel_url=url)
            
            # 2. Iniciar barrido de ciclos (Paginación)
            all_reviews = scraper.extract_all_reviews()
            
            # 3. Empujar resultado completo a la memoria de transferencia del escritor central
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
    Orquestador Concurrente Principal.
    
    1. Filtra las URLs.
    2. Instancia la Cola (Queue) para compartición de objetos con control de hilos nativos.
    3. Inicia 1 Hilo singular de Escritorio CSV/BD (`csv_writer_listener`).
    4. Divide las URLs en N trozos matemáticamente proporcionales y crea `N` Hilos de Trabajo (`worker_process`).
    5. Coordina los cierres estructurales mediante mecanismos de Unión (`join`) y pastilla envenenada (`Poison Pill`).
    
    Args:
        hotel_urls (List[str]): Lista total de URLs de hoteles obtenida en Fase 1.
        processed_urls (Set[str], optional): Historial para evitar redundancia de extracción (generalmente vacío si se procesa directamente).
    """
    # Filtrar URLs ya procesadas (Medida de precaución de segunda capa)
    urls_to_process = [url for url in hotel_urls if url not in processed_urls]
    
    if not urls_to_process:
        logging.info("No hay nuevas URLs para procesar.")
        return

    logging.info(f"Iniciando pipeline para {len(urls_to_process)} hoteles con {config.MAX_WORKERS} workers.")

    # Cola transaccional para evitar race conditions a la hora de procesar inserciones DB (SQLite)
    result_queue = queue.Queue()
    
    # Iniciar Hilo Tarea Consumidor
    writer_thread = threading.Thread(
        target=csv_writer_listener,
        args=(result_queue, config.RAW_REVIEWS_FILE)
    )
    writer_thread.start()
    
    # Segmentación Matemática Dinámica (Chunks) del trabajo a repartir
    chunk_size = (len(urls_to_process) // config.MAX_WORKERS) + 1
    chunks = [urls_to_process[i:i + chunk_size] for i in range(0, len(urls_to_process), chunk_size)]
    
    # Iniciar enjambre Productor de Hilos (Workers)
    threads = []
    for i, chunk in enumerate(chunks):
        if not chunk: continue
        t = threading.Thread(target=worker_process, args=(chunk, result_queue, i+1))
        t.start()
        threads.append(t)
        
    # Sincronización 1: Esperar a que el equipo Productor acabe al 100% resolviendo llamadas HTTP
    for t in threads:
        t.join()
        
    # Mandar pastilla de finalización para destruir ciclo centinela del Consumidor
    result_queue.put(None)
    
    # Sincronización 2: Esperar a que el gestor SQLite haya vaciado exitosamente el total de la cola en memoria
    writer_thread.join()
    
    logging.info("Pipeline finalizado correctamente.")


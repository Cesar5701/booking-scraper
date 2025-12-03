import queue
import threading
import logging
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

                    try:
                        for item in batch:
                            # Generar Hash Único basado en campos clave
                            unique_str = f"{item.get('hotel_url')}{item.get('date')}{item.get('title')}{item.get('positive')}{item.get('negative')}"
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
                                review_hash=review_hash
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
                    if new_reviews_for_csv:
                        writer.writerows(new_reviews_for_csv)
                        f.flush()

                    logging.info(f"   [SAVED] Procesados {len(batch)}. Nuevos en DB/CSV: {saved_count}.")
                except Exception as e:
                    logging.error(f"Error escribiendo datos: {e}")
                finally:
                    result_queue.task_done()
        finally:
            db.close()

def worker_process(urls: List[str], result_queue: queue.Queue, worker_id: int, driver_path: str) -> None:
    """
    Función ejecutada por cada hilo worker para procesar una lista de URLs de hoteles.
    
    Args:
        urls (List[str]): Lista de URLs de hoteles asignada a este worker.
        result_queue (queue.Queue): Cola compartida para enviar los resultados (reseñas).
        worker_id (int): Identificador numérico del worker para logging.
        driver_path (str): Ruta al ejecutable del driver.
    """
    driver = initialize_driver(executable_path=driver_path)
    hotel_page = HotelPage(driver)
    
    logging.info(f"Worker {worker_id} iniciado. Procesando {len(urls)} URLs.")
    
    for url in urls:
        try:
            logging.info(f"Worker {worker_id} visitando: {url}")
            hotel_page.navigate(url)
            
            # Abrir modal de reseñas
            reviews_modal = hotel_page.open_reviews_modal()
            if not reviews_modal:
                logging.warning(f"Worker {worker_id}: No se pudo abrir modal para {url}")
                continue
            
            # Extraer reseñas
            all_reviews = reviews_modal.extract_all_reviews(max_reviews=config.MAX_REVIEWS_PER_HOTEL)
            
            if all_reviews:
                result_queue.put(all_reviews)
                logging.info(f"Worker {worker_id}: {len(all_reviews)} reseñas enviadas a cola para {url}")
            else:
                logging.warning(f"Worker {worker_id}: 0 reseñas extraídas para {url}")
                
        except Exception as e:
            logging.error(f"Worker {worker_id} error en {url}: {e}")
            # Importante: No detener el worker por un error en un hotel, seguir con el siguiente
            continue
            
    driver.quit()
    logging.info(f"Worker {worker_id} finalizado.")

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
    
    # Obtener ruta del driver UNA VEZ
    driver_path = get_driver_path()

    threads = []
    for i, chunk in enumerate(chunks):
        if not chunk: continue
        t = threading.Thread(target=worker_process, args=(chunk, result_queue, i+1, driver_path))
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

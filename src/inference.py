"""
Módulo de Inferencia de Procesamiento de Lenguaje Natural (PLN)

Aplica modelos de Deep Learning (Transformers tipo RoBERTuito/BERT) para clasificar
el sentimiento (Positivo, Negativo, Neutro) de las reseñas extraídas.

Características clave:
- Carga en memoria caché del modelo para evitar tiempos de cold-start reiterados.
- Procesamiento en bloques (Chunks) para mitigar desbordamientos de Memoria RAM/VRAM.
- Separación condicional por idioma detectado en tiempo de ejecución.
- Detección acelerada por GPU de existir soporte CUDA local.
"""
import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm
import numpy as np
from functools import lru_cache
import time

from src import config
from src.core.database import SessionLocal, engine, Base
from src.models import Review
from src.utils.cleaning import clean_text_basic, build_clean_review_text
from src.utils.language import detect_language_safe



@lru_cache(maxsize=2)
def get_analyzer(lang: str):
    """
    Carga y mantiene en caché (Memoria RAM/VRAM) el modelo de análisis de sentimientos de `PySentimiento`
    para un idioma específico. El decorador `lru_cache` garantiza que si invocamos repetidamente 'es', 
    el motor retorne la instancia pre-cargada instantáneamente en lugar de descargar o reinstanciar pesos.
    
    Args:
        lang (str): Código ISO-639-1 del idioma (ej: 'es', 'en').
        
    Returns:
        Analyzer: Instancia del modelo transformer inicializado.
    """
    # Preferencia nativa de aceleración por Hardware (0 = Primer GPU CUDA, -1 = CPU Computación Clásica)
    device = 0 if torch.cuda.is_available() else -1
    print(f"[INFO] Loading analyzer for '{lang}' on {'cuda' if device == 0 else 'cpu'}...")
    return create_analyzer(task="sentiment", lang=lang, device=device)



def main():
    """
    Orquestador de inferencia transaccional.
    
    Flujo:
    1. Lee de la Base de Datos SQLite todas las reseñas con Label=None (es decir, recién scrapeadas).
    2. Modula la cantidad por "CHUNK_SIZE" (Ej. 500) para evadir Memory Leaks.
    3. Para cada iteración:
       a) Limpia el marcador vacío ('Esta entrada no tiene comentarios') y une cláusulas con puntuación ('. ').
       b) Ejecuta rutina de limpieza ligera y detecta idioma (FastText).
       c) Agrupa por conjuntos 'Español' e 'Inglés'.
       d) Aplica la rutina matricial `_run_inference` a las redes neuronales por conjunto idiomático respectivo.
    4. Cierra y comete transacción general contra la BD para reflejar las etiquetas probabilísticas generadas.
    """
    # Crear tablas si no existen en la cadena relacional
    Base.metadata.create_all(bind=engine)
    
    print(f"[INFO] Connecting to Database: {config.DATABASE_URL}")
    db = SessionLocal()
    
    try:
        # 1. Recuperar Universo Limpio (Registros pendientes sin procesar)
        total_reviews = db.query(Review).filter(Review.sentiment_label.is_(None)).count()
        print(f"[INFO] Found {total_reviews} un-processed reviews in DB.")
        
        if total_reviews == 0:
            print("[INFO] No new reviews found in Database.")
            return

        # --- ESTRATEGIA DE PROCESAMIENTO EN BLOQUES (CHUNK PROCESSING) ---
        print("[INFO] Starting chunk processing to avoid memory and session issues...")
        
        CHUNK_SIZE = 500
        
        # Variables de Control y Telemetría
        total_lang_time = 0
        total_inf_time = 0
        total_db_time = 0
        
        for _ in range(0, total_reviews, CHUNK_SIZE):
            # Extraer Trozo Limitado directamente desde SQL nativo para no asfixiar memoria SQLAlchemy ORM
            chunk = db.query(Review).filter(Review.sentiment_label.is_(None)).limit(CHUNK_SIZE).all()
            if not chunk:
                break
                
            start_lang = time.time()
            batch_es = []
            batch_en = []
            
            for review in chunk:
                # 3a. Preprocesamiento: Verificar que exista cuerpo escrito por el huésped (sin marcador vacío)
                body_only = build_clean_review_text(review.positive, review.negative)
                if not body_only:
                    review.full_review_processed = ""
                    review.language = "unknown"
                    review.sentiment_label = "NO_TEXT"
                    review.sentiment_score_pos = None
                    review.sentiment_score_neg = None
                    review.sentiment_score_neu = None
                    continue

                processed = build_clean_review_text(
                    review.positive, review.negative, include_title=review.title
                )
                review.full_review_processed = processed
                
                # 3b. Detección Inteligente e Inserción a Lista (Clustering Simple)
                lang = detect_language_safe(body_only)
                review.language = lang
                if lang == 'es':
                    batch_es.append(review)
                else:
                    # Todo lo no-español lo mandamos por fallback a motor inglés para simplificación analítica
                    batch_en.append(review)
            total_lang_time += (time.time() - start_lang)
            
            # 3d. Rutina Disparadora de Inferencia Discreta
            start_inf = time.time()
            if batch_es:
                _run_inference(batch_es, 'es')
            if batch_en:
                _run_inference(batch_en, 'en')
            total_inf_time += (time.time() - start_inf)
            
            # 4. Inserción Atómica a la Transacción
            start_db = time.time()
            db.commit()
            total_db_time += (time.time() - start_db)

        # Resumen Estadístico de Overhead Computacional
        print(f"[TIMING] Language/Cleaning total time: {total_lang_time:.2f}s")
        print(f"[TIMING] Inference Model total time: {total_inf_time:.2f}s")
        print(f"[TIMING] DB Commit total time: {total_db_time:.2f}s")
        print("[INFO] Done! Database updated.")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        # Retroceder si algo sale mal (Ej. Out of Memory Crash de CUDA)
        db.rollback()
    finally:
        db.close()


def predict_in_batches(analyzer, texts, lang, batch_size=32):
    """
    Ejecuta inferencia neuronal en sub-lotes (batch_size) para optimizar VRAM.
    """
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        results.extend(analyzer.predict(batch))
    return results


def _run_inference(reviews_list, lang):
    """
    Función vectorizada de ayuda que empaqueta las reseñas y procesa utilizando la librería de Transformer activa.
    
    Args:
        reviews_list (List[Review]): Colección de Objetos Review (ORM).
        lang (str): Abreviatura de dialecto objetivo (es, en).
    """
    analyzer = get_analyzer(lang)
    texts = [r.full_review_processed for r in reviews_list]
    preds = predict_in_batches(analyzer, texts, lang, batch_size=64)
    
    # Desempaquetar salidas enlazándolas con los modelos objetos de las reviews base
    for r, p in zip(reviews_list, preds):
        r.sentiment_label = p.output # "POS", "NEG", "NEU"
        r.sentiment_score_pos = p.probas.get('POS', 0.0) # Probabilidad Flotante Ej: 0.985
        r.sentiment_score_neg = p.probas.get('NEG', 0.0)
        r.sentiment_score_neu = p.probas.get('NEU', 0.0)

if __name__ == "__main__":
    main()

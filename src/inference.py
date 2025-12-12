import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm
import numpy as np
from functools import lru_cache

from src import config
from src.core.database import SessionLocal, engine, Base
from src.models import Review
from src.utils.cleaning import clean_text_basic
from src.utils.language import detect_language_safe



@lru_cache(maxsize=2)
def get_analyzer(lang: str):
    """
    Carga y cachea el modelo de análisis de sentimientos para un idioma dado.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Loading analyzer for '{lang}' on {device}...")
    return create_analyzer(task="sentiment", lang=lang)



def main():
    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    print(f"[INFO] Connecting to Database: {config.DATABASE_URL}")
    db = SessionLocal()
    
    try:
        # 1. Contar total de reseñas para informar
        total_reviews = db.query(Review).count()
        print(f"[INFO] Found {total_reviews} reviews in DB.")
        
        if total_reviews == 0:
            print("[ERROR] No reviews found in Database. Run scraper first.")
            return

        # --- PROCESSING IN BATCHES ---
        print("[INFO] Starting batch processing...")
        
        # Tamaño del lote para lectura de DB
        DB_BATCH_SIZE = 1000
        
        # Query con yield_per para no cargar todo en RAM
        query = db.query(Review).yield_per(DB_BATCH_SIZE)
        
        batch_buffer = []
        
        for i, review in enumerate(tqdm(query, total=total_reviews, desc="Processing Reviews")):
            # Preprocessing
            full_text = f"{review.title or ''} {review.positive or ''} {review.negative or ''}".strip()
            processed = clean_text_basic(full_text)
            review.full_review_processed = processed
            
            lang = detect_language_safe(processed)
            review.language = lang
            
            if lang in ['es', 'en']:
                batch_buffer.append(review)
            
            # Procesar cuando el buffer se llena o es el último elemento
            if len(batch_buffer) >= config.BATCH_SIZE or (i + 1 == total_reviews and batch_buffer):
                _process_inference_batch(batch_buffer)
                batch_buffer = [] # Limpiar buffer
                
                # Commit parcial para guardar progreso y liberar memoria de la sesión si fuera necesario
                # (Aunque yield_per mantiene la sesión activa, commit es seguro aquí)
                db.commit()
                # Liberar objetos de la sesión para liberar memoria
                db.expunge_all()

        print("[INFO] Done! Database updated.")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        db.rollback()
    finally:
        db.close()

def _process_inference_batch(reviews_batch):
    """
    Helper function to process a small batch of reviews for inference.
    """
    reviews_es = [r for r in reviews_batch if r.language == 'es']
    reviews_en = [r for r in reviews_batch if r.language == 'en']

    # Procesar Español
    if reviews_es:
        analyzer_es = get_analyzer('es')
        texts = [r.full_review_processed for r in reviews_es]
        # Ya estamos en un lote pequeño, así que llamamos predict directamente o usamos predict_in_batches con size total
        preds = analyzer_es.predict(texts)
        
        for r, p in zip(reviews_es, preds):
            r.sentiment_label = p.output
            r.sentiment_score_pos = p.probas.get('POS', 0.0)
            r.sentiment_score_neg = p.probas.get('NEG', 0.0)
            r.sentiment_score_neu = p.probas.get('NEU', 0.0)

    # Procesar Inglés
    if reviews_en:
        analyzer_en = get_analyzer('en')
        texts = [r.full_review_processed for r in reviews_en]
        preds = analyzer_en.predict(texts)
        
        for r, p in zip(reviews_en, preds):
            r.sentiment_label = p.output
            r.sentiment_score_pos = p.probas.get('POS', 0.0)
            r.sentiment_score_neg = p.probas.get('NEG', 0.0)
            r.sentiment_score_neu = p.probas.get('NEU', 0.0)

if __name__ == "__main__":
    main()

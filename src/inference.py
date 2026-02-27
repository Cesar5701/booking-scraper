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
from src.utils.cleaning import clean_text_basic
from src.utils.language import detect_language_safe



@lru_cache(maxsize=2)
def get_analyzer(lang: str):
    """
    Carga y cachea el modelo de análisis de sentimientos para un idioma dado.
    """
    device = 0 if torch.cuda.is_available() else -1
    print(f"[INFO] Loading analyzer for '{lang}' on {'cuda' if device == 0 else 'cpu'}...")
    return create_analyzer(task="sentiment", lang=lang, device=device)



def main():
    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    print(f"[INFO] Connecting to Database: {config.DATABASE_URL}")
    db = SessionLocal()
    
    try:
        # 1. Contar total de reseñas para informar
        total_reviews = db.query(Review).filter(Review.sentiment_label.is_(None)).count()
        print(f"[INFO] Found {total_reviews} un-processed reviews in DB.")
        
        if total_reviews == 0:
            print("[INFO] No new reviews found in Database.")
            return

        # --- PROCESSING IN CHUNKS ---
        print("[INFO] Starting chunk processing to avoid memory and session issues...")
        
        CHUNK_SIZE = 500
        
        total_lang_time = 0
        total_inf_time = 0
        total_db_time = 0
        
        for _ in range(0, total_reviews, CHUNK_SIZE):
            chunk = db.query(Review).filter(Review.sentiment_label.is_(None)).limit(CHUNK_SIZE).all()
            if not chunk:
                break
                
            start_lang = time.time()
            batch_es = []
            batch_en = []
            
            for review in chunk:
                # Preprocessing
                full_text = f"{review.title or ''} {review.positive or ''} {review.negative or ''}".strip()
                processed = clean_text_basic(full_text)
                review.full_review_processed = processed
                
                lang = detect_language_safe(processed)
                review.language = lang
                if lang == 'es':
                    batch_es.append(review)
                elif lang == 'en':
                    batch_en.append(review)
                else:
                    review.sentiment_label = 'SKIPPED'
            total_lang_time += (time.time() - start_lang)
            
            start_inf = time.time()
            if batch_es:
                _run_inference(batch_es, 'es')
            if batch_en:
                _run_inference(batch_en, 'en')
            total_inf_time += (time.time() - start_inf)
            
            start_db = time.time()
            db.commit()
            total_db_time += (time.time() - start_db)

        print(f"[TIMING] Language/Cleaning total time: {total_lang_time:.2f}s")
        print(f"[TIMING] Inference Model total time: {total_inf_time:.2f}s")
        print(f"[TIMING] DB Commit total time: {total_db_time:.2f}s")
        print("[INFO] Done! Database updated.")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        db.rollback()
    finally:
        db.close()

def _run_inference(reviews_list, lang):
    """
    Helper function to process a batch of reviews of a specific language for inference.
    """
    analyzer = get_analyzer(lang)
    texts = [r.full_review_processed for r in reviews_list]
    
    # analyzer.predict acepta listas, batch size optimizado
    preds = analyzer.predict(texts)
    
    for r, p in zip(reviews_list, preds):
        r.sentiment_label = p.output
        r.sentiment_score_pos = p.probas.get('POS', 0.0)
        r.sentiment_score_neg = p.probas.get('NEG', 0.0)
        r.sentiment_score_neu = p.probas.get('NEU', 0.0)

if __name__ == "__main__":
    main()

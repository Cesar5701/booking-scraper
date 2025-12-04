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

def predict_in_batches(analyzer, texts, lang_code, batch_size=config.BATCH_SIZE):
    """
    Realiza predicciones en lotes para evitar sobrecarga de memoria y mejorar velocidad.
    """
    results = []
    for i in tqdm(range(0, len(texts), batch_size), desc=f"Processing batches ({lang_code})"):
        batch = texts[i:i + batch_size]
        # pysentimiento acepta listas de strings
        batch_predictions = analyzer.predict(batch)
        results.extend(batch_predictions)
    return results

def predict_sentiment_multilingual(df):
    """
    Aplica el modelo correcto según el idioma de la fila usando procesamiento por lotes.
    Carga los modelos automáticamente usando get_analyzer.
    """
    # Inicializar columnas de resultados con valores nulos/vacíos
    df['sentiment_label'] = None
    df['sentiment_score_pos'] = 0.0
    df['sentiment_score_neg'] = 0.0
    df['sentiment_score_neu'] = 0.0

    # --- PROCESAR INGLÉS ---
    print("\n[EN] Processing English reviews...")
    mask_en = df['language'] == 'en'
    df_en = df[mask_en]
    
    if not df_en.empty:
        analyzer_en = get_analyzer('en')
        texts_en = df_en['full_review_processed'].astype(str).tolist()
        preds_en = predict_in_batches(analyzer_en, texts_en, 'en')
        
        # Asignar resultados usando el índice original
        df.loc[mask_en, 'sentiment_label'] = [p.output for p in preds_en]
        df.loc[mask_en, 'sentiment_score_pos'] = [p.probas.get('POS', 0) for p in preds_en]
        df.loc[mask_en, 'sentiment_score_neg'] = [p.probas.get('NEG', 0) for p in preds_en]
        df.loc[mask_en, 'sentiment_score_neu'] = [p.probas.get('NEU', 0) for p in preds_en]

    # --- PROCESAR ESPAÑOL Y OTROS (FALLBACK) ---
    print("\n[ES] Processing Spanish/Other reviews...")
    # Todo lo que no sea 'en' se procesa con el modelo en español
    mask_es = df['language'] == 'es'
    df_es = df[mask_es]
    
    if not df_es.empty:
        analyzer_es = get_analyzer('es')
        texts_es = df_es['full_review_processed'].astype(str).tolist()
        preds_es = predict_in_batches(analyzer_es, texts_es, 'es')
        
        # Asignar resultados
        df.loc[mask_es, 'sentiment_label'] = [p.output for p in preds_es]
        df.loc[mask_es, 'sentiment_score_pos'] = [p.probas.get('POS', 0) for p in preds_es]
        df.loc[mask_es, 'sentiment_score_neg'] = [p.probas.get('NEG', 0) for p in preds_es]
        df.loc[mask_es, 'sentiment_score_neu'] = [p.probas.get('NEU', 0) for p in preds_es]

    return df

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

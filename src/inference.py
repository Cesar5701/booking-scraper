import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm
import numpy as np

import config
from core.database import SessionLocal, engine, Base
from models import Review
from utils.cleaning import clean_text_basic
from utils.language import detect_language_safe

# Crear tablas si no existen (útil si se borró la DB)
Base.metadata.create_all(bind=engine)

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

def predict_sentiment_multilingual(df, analyzer_es, analyzer_en):
    """
    Aplica el modelo correcto según el idioma de la fila usando procesamiento por lotes.
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
    # REFACTOR: Usamos explícitamente 'es' para evitar errores si se añaden más idiomas
    mask_es = df['language'] == 'es'
    df_es = df[mask_es]
    
    if not df_es.empty:
        texts_es = df_es['full_review_processed'].astype(str).tolist()
        preds_es = predict_in_batches(analyzer_es, texts_es, 'es')
        
        # Asignar resultados
        df.loc[mask_es, 'sentiment_label'] = [p.output for p in preds_es]
        df.loc[mask_es, 'sentiment_score_pos'] = [p.probas.get('POS', 0) for p in preds_es]
        df.loc[mask_es, 'sentiment_score_neg'] = [p.probas.get('NEG', 0) for p in preds_es]
        df.loc[mask_es, 'sentiment_score_neu'] = [p.probas.get('NEU', 0) for p in preds_es]

    return df

def main():
    print(f"[INFO] Connecting to Database: {config.DATABASE_URL}")
    db = SessionLocal()
    
    try:
        # 1. Leer reseñas de la DB que no tengan sentimiento calculado
        # Opcional: Procesar todas. Por ahora, procesamos todas.
        reviews = db.query(Review).all()
        
        if not reviews:
            print("[ERROR] No reviews found in Database. Run scraper first.")
            return

        print(f"[INFO] Found {len(reviews)} reviews in DB.")
        
        # Convertir a DataFrame para facilitar el manejo (aunque podríamos iterar objetos)
        # Usamos objetos para poder actualizar fácilmente
        
        # --- PREPROCESSING ---
        print("[INFO] Preprocessing and Detecting Language...")
        valid_reviews = []
        
        for r in tqdm(reviews, desc="Preprocessing"):
            # Combinar título y cuerpo
            full_text = f"{r.title or ''} {r.positive or ''} {r.negative or ''}".strip()
            
            # Limpieza
            processed = clean_text_basic(full_text)
            r.full_review_processed = processed
            
            # Idioma
            lang = detect_language_safe(processed)
            r.language = lang
            
            if lang in ['es', 'en']:
                valid_reviews.append(r)
        
        db.commit() # Guardar progreso de preprocesamiento
        print(f"[INFO] Valid reviews for inference (ES/EN): {len(valid_reviews)}")

        # --- INFERENCE ---
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] Initializing analyzers on: {device}")
        
        analyzer_es = create_analyzer(task="sentiment", lang="es")
        analyzer_en = create_analyzer(task="sentiment", lang="en")

        # Separar por idioma
        reviews_es = [r for r in valid_reviews if r.language == 'es']
        reviews_en = [r for r in valid_reviews if r.language == 'en']

        # Procesar Español
        if reviews_es:
            print(f"\n[ES] Processing {len(reviews_es)} Spanish reviews...")
            texts = [r.full_review_processed for r in reviews_es]
            preds = predict_in_batches(analyzer_es, texts, 'es')
            
            for r, p in zip(reviews_es, preds):
                r.sentiment_label = p.output
                r.sentiment_score_pos = p.probas.get('POS', 0.0)
                r.sentiment_score_neg = p.probas.get('NEG', 0.0)
                r.sentiment_score_neu = p.probas.get('NEU', 0.0)

        # Procesar Inglés
        if reviews_en:
            print(f"\n[EN] Processing {len(reviews_en)} English reviews...")
            texts = [r.full_review_processed for r in reviews_en]
            preds = predict_in_batches(analyzer_en, texts, 'en')
            
            for r, p in zip(reviews_en, preds):
                r.sentiment_label = p.output
                r.sentiment_score_pos = p.probas.get('POS', 0.0)
                r.sentiment_score_neg = p.probas.get('NEG', 0.0)
                r.sentiment_score_neu = p.probas.get('NEU', 0.0)

        # --- SAVE ---
        print("[INFO] Saving results to Database...")
        db.commit()
        print("[INFO] Done! Database updated.")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
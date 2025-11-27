import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm
import numpy as np

import config

# --- CONFIGURATION ---
# Variables importadas de config.py

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
    print("\n🇺🇸 Processing English reviews...")
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
    print("\n🇲🇽 Processing Spanish/Other reviews...")
    # Todo lo que no sea 'en' se procesa con el modelo en español
    mask_es = df['language'] != 'en'
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
    print(f"📄 Reading data from '{config.PROCESSED_REVIEWS_FILE}'...")
    try:
        df = pd.read_csv(config.PROCESSED_REVIEWS_FILE)
    except FileNotFoundError:
        print(f"❌ File '{config.PROCESSED_REVIEWS_FILE}' not found.")
        return

    # --- Model Initialization ---
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Initializing analyzers on: {device}")
    
    # CARGAMOS LOS DOS MODELOS
    print("   1. Loading Spanish Analyzer (RoBERTuito)...")
    analyzer_es = create_analyzer(task="sentiment", lang="es")
    
    print("   2. Loading English Analyzer (RoBERTa)...")
    analyzer_en = create_analyzer(task="sentiment", lang="en")

    # --- Sentiment Analysis ---
    df_result = predict_sentiment_multilingual(df, analyzer_es, analyzer_en)

    print(f"💾 Saving final data to '{config.SENTIMENT_REVIEWS_FILE}'...")
    df_result.to_csv(config.SENTIMENT_REVIEWS_FILE, index=False, encoding='utf-8')
    print("🏁 Done!")

if __name__ == "__main__":
    main()
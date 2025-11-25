import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_FILE = "reviews_processed.csv"
OUTPUT_FILE = "reviews_with_sentiment.csv"

def predict_sentiment_multilingual(df, analyzer_es, analyzer_en):
    """
    Aplica el modelo correcto según el idioma de la fila.
    """
    results = []
    
    print("🧠 Analyzing sentiment...")
    for _, row in tqdm(df.iterrows(), total=len(df)):
        text = row['full_review_processed']
        lang = row['language']
        
        # Seleccionar el cerebro adecuado
        if lang == 'en':
            prediction = analyzer_en.predict(text)
        else:
            # Por defecto usamos español (es) para 'es' o casos raros
            prediction = analyzer_es.predict(text)
            
        results.append(prediction)
        
    return results

def main():
    print(f"📄 Reading data from '{INPUT_FILE}'...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"❌ File '{INPUT_FILE}' not found.")
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
    predictions = predict_sentiment_multilingual(df, analyzer_es, analyzer_en)

    # --- Process Results ---
    df['sentiment_label'] = [pred.output for pred in predictions]
    df['sentiment_score_pos'] = [pred.probas.get('POS', 0) for pred in predictions]
    df['sentiment_score_neg'] = [pred.probas.get('NEG', 0) for pred in predictions]
    df['sentiment_score_neu'] = [pred.probas.get('NEU', 0) for pred in predictions]

    print(f"💾 Saving final data to '{OUTPUT_FILE}'...")
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    print("🏁 Done!")

if __name__ == "__main__":
    main()
import pandas as pd
import re
import fasttext
import os

# Suprimir alertas de fasttext
fasttext.FastText.eprint = lambda x: None

import config

# --- CONFIGURATION ---
# Variables importadas de config.py

from utils.cleaning import clean_text_basic

# Cargar modelo FastText (Singleton)
MODEL_PATH = os.path.join(config.BASE_DIR, "lid.176.ftz")
FT_MODEL = None

def load_fasttext_model():
    global FT_MODEL
    if FT_MODEL is None:
        if not os.path.exists(MODEL_PATH):
            print("⬇️ Downloading FastText model (lid.176.ftz)...")
            import urllib.request
            url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
            urllib.request.urlretrieve(url, MODEL_PATH)
        
        print("🚀 Loading FastText model...")
        FT_MODEL = fasttext.load_model(MODEL_PATH)
    return FT_MODEL

def detect_language_safe(text):
    """Detecta si es 'es' (español), 'en' (inglés) u otro usando FastText."""
    if not text or len(text) < 3: return 'unknown'
    
    try:
        model = load_fasttext_model()
        # predict devuelve (('__label__es',), array([0.99]))
        prediction = model.predict(text.replace("\n", " "))
        label = prediction[0][0]
        lang = label.replace("__label__", "")
        return lang
    except Exception:
        return 'unknown'

def main():
    print(f"📄 Reading data from '{config.RAW_REVIEWS_FILE}'...")
    try:
        df = pd.read_csv(config.RAW_REVIEWS_FILE, on_bad_lines='skip')
    except FileNotFoundError:
        print("❌ File not found.")
        return

    # Combinar texto
    df['positive'] = df['positive'].fillna('')
    df['negative'] = df['negative'].fillna('')
    df['full_review'] = df['positive'] + ' ' + df['negative']
    
    # Filtrar vacíos
    df = df[df['full_review'].str.strip() != '']

    print("🚀 Detecting languages and cleaning text...")
    
    # 1. Limpieza suave
    df['full_review_processed'] = df['full_review'].apply(clean_text_basic)
    
    # 2. Detección de idioma (Crucial para el siguiente paso)
    # Esto creará una columna 'language' con 'es', 'en', etc.
    df['language'] = df['full_review_processed'].apply(detect_language_safe)
    
    # Opcional: Quedarnos solo con Inglés y Español para evitar errores
    df_filtered = df[df['language'].isin(['es', 'en'])].copy()
    
    print(f"📊 Reseñas encontradas: {len(df)}")
    print(f"✅ Reseñas útiles (ES/EN): {len(df_filtered)}")
    print(f"   - Español: {len(df_filtered[df_filtered['language']=='es'])}")
    print(f"   - Inglés:  {len(df_filtered[df_filtered['language']=='en'])}")

    print(f"💾 Saving to '{config.PROCESSED_REVIEWS_FILE}'...")
    df_filtered.to_csv(config.PROCESSED_REVIEWS_FILE, index=False, encoding='utf-8')

if __name__ == "__main__":
    main()
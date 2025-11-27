import pandas as pd
import re
from langdetect import detect, LangDetectException

import config

# --- CONFIGURATION ---
# Variables importadas de config.py

def clean_text_basic(text):
    """
    Limpieza básica para Transformers.
    No lematizamos para respetar la estructura de ambos idiomas.
    """
    if not isinstance(text, str):
        return ""
    # Convertir a minúsculas
    text = text.lower()
    # Eliminar espacios extra
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def detect_language_safe(text):
    """Detecta si es 'es' (español), 'en' (inglés) u otro."""
    try:
        if len(text) < 3: return 'unknown'
        return detect(text)
    except LangDetectException:
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
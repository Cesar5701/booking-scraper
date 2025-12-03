import fasttext
import os
from langdetect import detect, LangDetectException
from src import config

# Suprimir alertas de fasttext
fasttext.FastText.eprint = lambda x: None

# Cargar modelo FastText (Singleton)
MODEL_PATH = os.path.join(config.BASE_DIR, "lid.176.ftz")
FT_MODEL = None

def load_fasttext_model():
    global FT_MODEL
    if FT_MODEL is None:
        if not os.path.exists(MODEL_PATH):
            print("[INFO] Downloading FastText model (lid.176.ftz)...")
            import urllib.request
            url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
            urllib.request.urlretrieve(url, MODEL_PATH)
        
        print("[INFO] Loading FastText model...")
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

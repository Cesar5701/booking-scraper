import sys
import os
sys.path.append(os.getcwd())

from src.core.database import SessionLocal
from src.models import Review
from src.utils.cleaning import clean_text_basic
from src.utils.language import load_fasttext_model
from src import config

def main():
    print(f"Database URL: {config.DATABASE_URL}")
    db = SessionLocal()
    try:
        reviews = db.query(Review).limit(1).all()
        
        for r in reviews:
            print("-" * 20)
            full_text = f"{r.title or ''} {r.positive or ''} {r.negative or ''}".strip()
            cleaned = clean_text_basic(full_text)
            print(f"Cleaned: {repr(cleaned[:100])}")
            
            print("Attempting prediction with explicit error handling...")
            try:
                model = load_fasttext_model()
                # Replicating logic from src/utils/language.py
                prediction = model.predict(cleaned.replace("\n", " "))
                print(f"Raw Prediction: {prediction}")
                label = prediction[0][0]
                lang = label.replace("__label__", "")
                print(f"Detected Lang: {lang}")
            except Exception as e:
                print(f"CAUGHT EXCEPTION: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()

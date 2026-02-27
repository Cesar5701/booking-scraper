import pandas as pd
import config
from core.database import SessionLocal
from models import Review
import logging

def export_db_to_csv():
    print(f"[INFO] Connecting to Database: {config.DATABASE_URL}")
    db = SessionLocal()
    
    try:
        reviews = db.query(Review).all()
        if not reviews:
            print("[WARN] No reviews found in database.")
            return

        print(f"[INFO] Found {len(reviews)} reviews in DB. Exporting to CSV...")
        
        # Convert to list of dicts
        data = []
        for r in reviews:
            data.append({
                "hotel_name": r.hotel_name,
                "hotel_url": r.hotel_url,
                "title": r.title,
                "score": r.score,
                "positive": r.positive,
                "negative": r.negative,
                "date": r.date
            })
            
        df = pd.DataFrame(data)
        
        # Save to CSV
        output_file = config.RAW_REVIEWS_FILE
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"[SUCCESS] Exported {len(df)} reviews to '{output_file}'")
        
    except Exception as e:
        print(f"[ERROR] Failed to export: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    export_db_to_csv()

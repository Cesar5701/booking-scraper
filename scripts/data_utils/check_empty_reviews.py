from core.database import SessionLocal
from models import Review
from sqlalchemy import or_

def check_empty():
    db = SessionLocal()
    try:
        total = db.query(Review).count()
        # Count where positive AND negative are empty/null
        empty_body = db.query(Review).filter(
            (Review.positive == None) | (Review.positive == ''),
            (Review.negative == None) | (Review.negative == '')
        ).count()
        
        print(f"Total Reviews: {total}")
        print(f"Empty Body Reviews (No pos/neg): {empty_body}")
        print(f"Difference: {total - empty_body}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_empty()

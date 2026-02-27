import os
import sys

from src.core.database import SessionLocal
from src.models import Review

db = SessionLocal()
unprocessed = db.query(Review).filter(Review.sentiment_label == None).all()
print(f"Total unprocessed: {len(unprocessed)}")
for r in unprocessed[:5]:
    print(r.title, r.positive, r.negative, r.language)

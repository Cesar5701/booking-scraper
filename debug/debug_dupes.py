import os
import sys

from src.core.database import SessionLocal
from src.models import Review

db = SessionLocal()

total = db.query(Review).count()
print(f"Total reviews in DB: {total}")

from sqlalchemy import func

# Find duplicate hashes
duplicate_hashes = db.query(Review.review_hash, func.count(Review.id)).group_by(Review.review_hash).having(func.count(Review.id) > 1).all()
print(f"Number of distinct hashes with duplicates: {len(duplicate_hashes)}")

if duplicate_hashes:
    example_hash = duplicate_hashes[0][0]
    print(f"\nExample duplicate hash: {example_hash}")
    dupes = db.query(Review).filter(Review.review_hash == example_hash).all()
    for d in dupes:
        print(f"ID: {d.id} | Hotel: {d.hotel_name} | hash: {d.review_hash}")
        
# Check if there are exact duplicates by content but different hash
duplicate_contents = db.query(Review.title, Review.positive, Review.negative, func.count(Review.id)).group_by(Review.title, Review.positive, Review.negative).having(func.count(Review.id) > 1).limit(5).all()
print(f"\nNumber of content duplicates (title, pos, neg): {len(duplicate_contents)} showing up to 5")
for dc in duplicate_contents:
    print(dc)

db.close()

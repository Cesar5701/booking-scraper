import os
import sys

from src.core.database import SessionLocal
from src.models import Review

db = SessionLocal()

# Muestra algunas URLs para revisar si tienen parámetros variables
reviews = db.query(Review.hotel_url).limit(10).all()
for r in reviews:
    print(r.hotel_url)

# Verificar cuántos hoteles únicos hay limpios
counts = db.query(Review.hotel_name).distinct().count()
print(f"Distinct hotel names: {counts}")

distinct_urls = db.query(Review.hotel_url).distinct().count()
print(f"Distinct URLs: {distinct_urls}")

db.close()

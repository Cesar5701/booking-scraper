import os
import sys
import hashlib
from tqdm import tqdm

from src.core.database import SessionLocal
from src.models import Review

def clean_database():
    db = SessionLocal()
    
    # Obtener todas las reseñas
    all_reviews = db.query(Review).all()
    initial_count = len(all_reviews)
    print(f"Total registros iniciales: {initial_count}")
    
    unique_hashes = set()
    to_delete = []
    
    # Procesar y limpiar
    for r in tqdm(all_reviews, desc="Escaneando y normalizando"):
        # Limpiar URL
        clean_url = (r.hotel_url or '').split('?')[0]
        r.hotel_url = clean_url
        
        # Regenerar el verdadero Hash
        unique_str = f"{clean_url}{r.date}{r.title}{r.positive}{r.negative}"
        true_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        
        # Determinar si es un duplicado o hay que guardarlo
        if true_hash in unique_hashes:
            to_delete.append(r)
        else:
            unique_hashes.add(true_hash)
            # Actualizar el registro a su hash verdadero
            r.review_hash = true_hash
            
    # Realizar actualizaciones y purga
    print(f"\nSe encontraron {len(to_delete)} registros duplicados debido a URLs dinámicas.")
    if to_delete:
        print("Eliminando duplicados...")
        for d in tqdm(to_delete, desc="Borrando duplicados"):
            db.delete(d)
        
        print("Aplicando nuevos hashes y guardando cambios...")
        db.commit()
    
    final_count = db.query(Review).count()
    print(f"\nLimpieza completada. Base de datos reducida de {initial_count} a {final_count} registros.")
    
    db.close()

if __name__ == "__main__":
    clean_database()

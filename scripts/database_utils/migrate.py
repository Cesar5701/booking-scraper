import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "data", "reviews.db")
    if not os.path.exists(db_path):
        print("No DB found to migrate.")
        return
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN room_type VARCHAR;")
        print("Added room_type column.")
    except sqlite3.OperationalError as e:
        print(f"Skipping room_type: {e}")

    try:
        c.execute("ALTER TABLE reviews ADD COLUMN traveler_type VARCHAR;")
        print("Added traveler_type column.")
    except sqlite3.OperationalError as e:
        print(f"Skipping traveler_type: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()

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
        c.execute("ALTER TABLE reviews ADD COLUMN nationality VARCHAR;")
        print("Added nationality column.")
    except sqlite3.OperationalError as e:
        print(f"Skipping nationality: {e}")

    try:
        c.execute("ALTER TABLE reviews ADD COLUMN nights_stayed VARCHAR;")
        print("Added nights_stayed column.")
    except sqlite3.OperationalError as e:
        print(f"Skipping nights_stayed: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()

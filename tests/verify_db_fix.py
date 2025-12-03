import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.database import engine
from sqlalchemy import text

def verify_db():
    print("Verifying database connection and WAL mode...")
    try:
        with engine.connect() as conn:
            # Check Journal Mode
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
            print(f"Current Journal Mode: {result}")
            
            if result.upper() == 'WAL':
                print("SUCCESS: WAL mode is enabled.")
            else:
                print("FAILURE: WAL mode is NOT enabled.")
                
            # Check Table Access
            count = conn.execute(text("SELECT count(*) FROM reviews")).scalar()
            print(f"Reviews count: {count}")
            print("SUCCESS: Database is readable.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    verify_db()

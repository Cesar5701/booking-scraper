import pandas as pd
import os
import config

def clean_csv_duplicates():
    file_path = config.RAW_REVIEWS_FILE
    
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return

    print(f"[INFO] Reading {file_path}...")
    try:
        df = pd.read_csv(file_path)
        initial_count = len(df)
        
        print(f"[INFO] Initial row count: {initial_count}")
        
        # Remove duplicates based on all columns
        df_cleaned = df.drop_duplicates()
        final_count = len(df_cleaned)
        
        duplicates_removed = initial_count - final_count
        
        if duplicates_removed > 0:
            print(f"[INFO] Found and removed {duplicates_removed} duplicate rows.")
            df_cleaned.to_csv(file_path, index=False, encoding='utf-8')
            print(f"[SUCCESS] File saved. New row count: {final_count}")
        else:
            print("[INFO] No duplicates found.")
            
    except Exception as e:
        print(f"[ERROR] Failed to clean CSV: {e}")

if __name__ == "__main__":
    clean_csv_duplicates()

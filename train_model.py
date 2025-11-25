import pandas as pd
from pysentimiento import create_analyzer
import torch
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_FILE = "reviews_processed.csv"
OUTPUT_FILE = "reviews_with_sentiment.csv"

def analyze_sentiment_in_batches(analyzer, texts, batch_size=32):
    """
    Analyzes sentiment for a list of texts in batches to show progress
    and manage memory.
    """
    results = []
    # Using tqdm to create a progress bar
    for i in tqdm(range(0, len(texts), batch_size), desc="Analyzing Sentiment"):
        batch = texts[i:i+batch_size]
        # The library handles the prediction for the batch
        results.extend(analyzer.predict(batch))
    return results

def main():
    """
    Main function to load processed data, perform sentiment analysis,
    and save the final results.
    """
    print(f"📄 Reading processed data from '{INPUT_FILE}'...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"❌ ERROR: The file '{INPUT_FILE}' was not found.")
        print("Please make sure you have run the 'preprocess.py' script first.")
        return

    # --- Model Initialization ---
    # Check if a GPU is available for faster processing
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Initializing sentiment analyzer on device: {device}")
    # This will download the RoBERTuito model on the first run
    sentiment_analyzer = create_analyzer(task="sentiment", lang="es")

    # --- Data Preparation ---
    # Ensure the review column exists and handle potential empty reviews
    if 'full_review_processed' not in df.columns:
        print("❌ ERROR: Column 'full_review_processed' not found in the input file.")
        return
        
    # Convert column to list and replace non-string values with empty strings
    reviews = df['full_review_processed'].fillna('').astype(str).tolist()

    print(f"🧠 Found {len(reviews)} reviews to analyze. This will take some time...")

    # --- Sentiment Analysis ---
    predictions = analyze_sentiment_in_batches(sentiment_analyzer, reviews)

    # --- Process Results ---
    # Extract the main sentiment label (POS, NEG, NEU)
    df['sentiment_label'] = [pred.output for pred in predictions]

    # Extract the probabilities for each class
    df['sentiment_score_pos'] = [pred.probas['POS'] for pred in predictions]
    df['sentiment_score_neg'] = [pred.probas['NEG'] for pred in predictions]
    df['sentiment_score_neu'] = [pred.probas['NEU'] for pred in predictions]

    print(f"💾 Saving final data with sentiment scores to '{OUTPUT_FILE}'...")
    
    # --- Save Final Results ---
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    
    print("🏁 Sentiment analysis finished successfully!")
    print(f"Your final dataset is ready in '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()

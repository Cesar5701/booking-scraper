import pandas as pd
import spacy
import re
from spacy.lang.es.stop_words import STOP_WORDS
import unicodedata

# --- CONFIGURATION ---
INPUT_FILE = "tlaxcala_hotel_reviews_full.csv"
OUTPUT_FILE = "reviews_processed.csv"

# Load the spaCy model for Spanish
# Make sure to run: python -m spacy download es_core_news_sm
print("🔄 Loading spaCy model for Spanish (es_core_news_sm)...")
nlp = spacy.load("es_core_news_sm")
print("✅ spaCy model loaded.")

def clean_and_lemmatize_text(text):
    """
    Cleans, normalizes, and lemmatizes a given Spanish text.
    - Converts to lowercase.
    - Removes accents and special characters.
    - Lemmatizes words.
    - Removes stopwords.
    """
    # Ensure text is a string
    if not isinstance(text, str):
        return ""

    # 1. Normalize unicode characters (e.g., accents)
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    
    # 2. Convert to lowercase
    text = text.lower()
    
    # 3. Remove special characters, punctuation, and numbers
    text = re.sub(r'[^a-z\s]', '', text)
    
    # 4. Process the text with spaCy
    doc = nlp(text)
    
    # 5. Lemmatize and remove stopwords, keeping only tokens with alphabetic characters
    tokens = [
        token.lemma_ for token in doc 
        if token.is_alpha and token.lemma_ not in STOP_WORDS
    ]
    
    return " ".join(tokens)

def clean_date(date_str):
    """
    Cleans and converts a Spanish date string to a standard format (YYYY-MM-DD).
    Example input: 'Comentó el: 20 de julio de 2023' or 'Reviewed: 20 July 2023'
    """
    if not isinstance(date_str, str):
        return None

    # Unified regex for Spanish and English formats
    # Handles "20 de julio de 2023" and "20 July 2023"
    match = re.search(r'(\d{1,2})\s+(?:de\s+)?([a-zA-Z]+)\s+(?:de\s+)?(\d{4})', date_str)
    if not match:
        return None  # Return None if format is not recognized

    day, month_name, year = match.groups()

    month_map = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
        'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'may': '05', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }

    month = month_map.get(month_name.lower())
    if not month:
        return None

    # Pad day with leading zero if necessary
    return f"{year}-{month}-{day.zfill(2)}"


def main():
    """
    Main function to load data, preprocess it, and save the result.
    """
    print(f"📄 Reading data from '{INPUT_FILE}'...")
    try:
        # Use on_bad_lines='skip' to ignore problematic rows in the CSV
        df = pd.read_csv(INPUT_FILE, on_bad_lines='skip')
    except FileNotFoundError:
        print(f"❌ ERROR: The file '{INPUT_FILE}' was not found.")
        print("Please make sure you have run the scraper first and the file exists.")
        return

    # --- Data Cleaning and Combination ---
    # Combine positive and negative reviews into a single text column
    # Fill NaN values with an empty string to avoid errors
    df['positive'] = df['positive'].fillna('')
    df['negative'] = df['negative'].fillna('')
    df['full_review'] = df['positive'] + ' ' + df['negative']

    # Also process the title, as it can contain useful keywords
    df['title'] = df['title'].fillna('')

    print("🚀 Starting text preprocessing. This may take a while depending on the data size...")
    
    # --- Text Preprocessing ---
    # Apply the cleaning function to the relevant text columns
    df['full_review_processed'] = df['full_review'].apply(clean_and_lemmatize_text)
    df['title_processed'] = df['title'].apply(clean_and_lemmatize_text)
    
    print(f"💾 Saving processed data to '{OUTPUT_FILE}'...")
    
    # --- Save Results ---
    # Save all original and newly created columns to the output file
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    
    print("🏁 Preprocessing finished successfully!")
    print(f"Your processed data is ready in '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()

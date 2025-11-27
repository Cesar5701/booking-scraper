# --- CONFIGURACIÓN GLOBAL ---

# URLs
SEARCH_URL = "https://www.booking.com/searchresults.html?ss=Tlaxcala%2C+Tlaxcala%2C+M%C3%A9xico&lang=es"

# Archivos (Rutas relativas o absolutas)
LINKS_FILE = "tlaxcala_hotel_links.csv"
RAW_REVIEWS_FILE = "tlaxcala_hotel_reviews_full.csv"
PROCESSED_REVIEWS_FILE = "reviews_processed.csv"
SENTIMENT_REVIEWS_FILE = "reviews_with_sentiment.csv"

# Scraper Settings
HEADLESS_MODE = False
MAX_WAIT_TIME = 10
HOTEL_VISIT_LIMIT = 0  # 0 = Todos
TIME_BETWEEN_PAGES_MIN = 2.0
TIME_BETWEEN_PAGES_MAX = 3.5

# Inference Settings
BATCH_SIZE = 32

# Dashboard / Cleaning Settings
MONTH_TRANSLATIONS = {
    "enero": "January", "febrero": "February", "marzo": "March", "abril": "April",
    "mayo": "May", "junio": "June", "julio": "July", "agosto": "August",
    "septiembre": "September", "octubre": "October", "noviembre": "November", "diciembre": "December"
}

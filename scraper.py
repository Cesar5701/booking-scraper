import csv
import time
import os
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# --- SCRAPER CONFIGURATION ---
SEARCH_URL = "https://www.booking.com/searchresults.html?ss=Tlaxcala%2C+Tlaxcala%2C+M%C3%A9xico&lang=en-gb"
HEADLESS_MODE = True  # Set to True to run the browser in the background

# Limits and Timings
MAX_WAIT_TIME = 10
HOTEL_VISIT_LIMIT = 0  # ⚠️ SET TO 0 TO DOWNLOAD ALL
TIME_BETWEEN_PAGES_MIN = 1.5
TIME_BETWEEN_PAGES_MAX = 2.5

# Output Files
FILE_LINKS = "tlaxcala_hotel_links.csv"
FILE_REVIEWS = "tlaxcala_hotel_reviews_full.csv"


def initialize_driver():
    """Initializes Chrome with anti-detection options and automatic driver management."""
    print("🚀 Initializing WebDriver...")
    options = Options()
    if HEADLESS_MODE:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def save_to_csv_append(data, filename, headers):
    """Saves data in 'append' mode to avoid losing progress."""
    if not data: return
    
    file_exists = os.path.isfile(filename)
    
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)
    print(f"   💾 {len(data)} reviews saved to '{filename}'.")


def get_all_hotel_links(driver, url):
    """Phase 1: Traverse search results, scroll, and click 'Load more'."""
    print(f"🌍 Navigating to: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, MAX_WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="property-card"]'))
        )
    except TimeoutException:
        print("❌ Initial results did not load. Aborting.")
        return []

    print("🔄 Loading full list (Scroll + 'Load more' button)...")
    scroll_attempts = 0
    max_attempts_stuck = 3

    while scroll_attempts < max_attempts_stuck:
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(1.5, 2.5))
        
        try:
            load_more_btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Load more results') or contains(., 'Cargar más resultados')]"))
            )
            driver.execute_script("arguments[0].click();", load_more_btn)
            print("   👉 'Load more' button clicked.")
            
            WebDriverWait(driver, MAX_WAIT_TIME).until(
                lambda d: d.execute_script("return document.body.scrollHeight") > last_height
            )
            scroll_attempts = 0
        except TimeoutException:
            scroll_attempts += 1
    
    print("\n🔍 Extracting final links...")
    elements = driver.find_elements(By.CSS_SELECTOR, 'a[data-testid="title-link"]')
    links = list(dict.fromkeys([e.get_attribute("href") for e in elements if e.get_attribute("href")]))
    
    print(f"🔗 TOTAL HOTELS FOUND: {len(links)}")
    
    with open(FILE_LINKS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hotel_link"])
        for l in links: writer.writerow([l])
        
    return links

def _get_safe_text(element, selector):
    """Safe text extraction helper to keep the code clean."""
    try:
        return element.find_element(By.CSS_SELECTOR, selector).text.strip()
    except NoSuchElementException:
        return ""

def extract_reviews_from_hotel(driver, hotel_url):
    """Phase 2: Enter hotel, get name, open reviews, and paginate to the end."""
    driver.get(hotel_url)
    time.sleep(random.uniform(2.0, 3.0))

    # Extract hotel name
    hotel_name = _get_safe_text(driver, 'h2[data-testid="post-booking-header-title"]')
    if not hotel_name:
        hotel_name = _get_safe_text(driver, '.pp-header__title') # Fallback selector

    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Dismiss sign-in info."], button[aria-label="Ignorar información sobre el inicio de sesión."]'))
        ).click()
    except: pass

    strategies = [
        (By.CSS_SELECTOR, '[data-testid="review-score-link"]'),
        (By.CSS_SELECTOR, '[data-testid="guest-reviews-tab-trigger"]'),
        (By.XPATH, "//a[contains(@href, '#tab-reviews')]"),
        (By.XPATH, "//*[contains(text(), 'Guest reviews') or contains(text(), 'Comentarios')]")
    ]
    
    reviews_opened = False
    for by, selector in strategies:
        try:
            elem = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].click();", elem)
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="review"]')))
            reviews_opened = True
            break
        except: continue

    if not reviews_opened:
        print("   ⚠️ Could not open reviews panel (or hotel has no reviews).")
        return []

    collected_reviews = []
    page = 1
    
    while True:
        try:
            review_elements = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="review"]'))
            )
        except TimeoutException:
            break

        for review in review_elements:
            try:
                title = _get_safe_text(review, '[data-testid="review-title"]')
                score_text = _get_safe_text(review, '[data-testid="review-score"]')
                score = score_text.replace("Score:", "").replace("Puntuación:", "").strip()
                pos = _get_safe_text(review, '[data-testid="review-positive-text"]')
                neg = _get_safe_text(review, '[data-testid="review-negative-text"]')
                date = _get_safe_text(review, '[data-testid="review-date"]')
                country = _get_safe_text(review, '[data-testid="review-author-country"] span')

                data = {
                    "hotel_name": hotel_name, "hotel_url": hotel_url, "title": title, "score": score,
                    "positive": pos, "negative": neg, "date": date, "country": country
                }
                if data not in collected_reviews:
                    collected_reviews.append(data)
            except StaleElementReferenceException:
                continue

        try:
            next_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Next page') or contains(@aria-label, 'Página siguiente')]")
            if next_btn.is_enabled() and next_btn.is_displayed():
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(TIME_BETWEEN_PAGES_MIN, TIME_BETWEEN_PAGES_MAX))
                page += 1
            else:
                break 
        except NoSuchElementException:
            break
        except Exception as e:
            print(f"      ⚠️ Error during pagination: {e}")
            break

    return collected_reviews


def main():
    # --- Resume Logic: Load already processed hotel URLs ---
    processed_urls = set()
    if os.path.isfile(FILE_REVIEWS):
        try:
            df = pd.read_csv(FILE_REVIEWS)
            processed_urls = set(df['hotel_url'].unique())
            print(f"✅ Resume logic enabled. Found {len(processed_urls)} already processed hotels.")
        except (pd.errors.EmptyDataError, KeyError):
             print(f"⚠️ Reviews file '{FILE_REVIEWS}' is empty or invalid. Starting from scratch.")
             pass


    driver = initialize_driver()
    
    try:
        links = get_all_hotel_links(driver, SEARCH_URL)
        
        if not links:
            print("🛑 No hotels found.")
            return

        if HOTEL_VISIT_LIMIT > 0:
            print(f"\n⚠️ TEST MODE: Processing only the first {HOTEL_VISIT_LIMIT} hotels.")
            links_to_process = links[:HOTEL_VISIT_LIMIT]
        else:
            print(f"\n🚀 FULL MODE: Processing all {len(links)} found hotels.")
            links_to_process = links

        review_headers = ["hotel_name", "hotel_url", "title", "score", "positive", "negative", "date", "country"]
        total = len(links_to_process)
        
        for i, link in enumerate(links_to_process):
            if link in processed_urls:
                print(f"⏭️ ({i+1}/{total}) Skipping already processed hotel: {link}")
                continue

            print(f"\n🏨 ({i+1}/{total}) Processing hotel: {link}")
            
            try:
                reviews = extract_reviews_from_hotel(driver, link)
                if reviews:
                    print(f"   ✅ Extracted {len(reviews)} total reviews.")
                    save_to_csv_append(reviews, FILE_REVIEWS, review_headers)
                else:
                    print("   ℹ️ No reviews captured.")
            except Exception as e:
                print(f"   ❌ Critical error on this hotel: {e}")

    finally:
        print("\n🏁 Process finished. Closing browser.")
        driver.quit()

if __name__ == "__main__":
    main()
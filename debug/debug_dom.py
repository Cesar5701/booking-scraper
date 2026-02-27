import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.core.driver import initialize_driver
from src.booking_selectors import Reviews, HotelPage

def inspect_review():
    url = "https://www.booking.com/hotel/mx/fiore-master-en-valquirico.es-mx.html"
    print(f"Loading {url}")
    driver = initialize_driver()
    try:
        driver.get(url)
        time.sleep(3)
        
        # Intentar clickear en ver reseñas
        reviews_links = driver.find_elements(By.CSS_SELECTOR, '.js-review-tab-link, [data-testid="review-score-link"]')
        if reviews_links:
            reviews_links[0].click()
            time.sleep(3)
            
        print("Looking for reviews...")
        reviews = driver.find_elements(By.CSS_SELECTOR, Reviews.ITEM)
        print(f"Found {len(reviews)} reviews")
        
        if reviews:
            r = reviews[0]
            print("\n--- FIRST REVIEW HTML DUMP ---")
            print(r.get_attribute('innerHTML')[:2000])
            
            print("\n--- TEXT CHUNKS ---")
            for text_elem in r.find_elements(By.XPATH, ".//*[string-length(normalize-space(text())) > 0]"):
                print(f"Tag: {text_elem.tag_name}, Class: {text_elem.get_attribute('class')}, Text: {text_elem.text}")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    inspect_review()

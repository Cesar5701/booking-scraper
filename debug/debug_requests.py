import requests
from bs4 import BeautifulSoup
import time

def test_requests_scraper():
    # Booking usa una ruta Ajax con offset para reseñas
    # Format: https://www.booking.com/reviewlist.es.html?pagename=<hotel_id>&cc1=mx&type=total&offset=0&rows=10
    
    url = "https://www.booking.com/reviewlist.es.html?pagename=fiore-master-en-valquirico&cc1=mx&type=total&offset=0&rows=10"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    print("Testing hidden internal API...")
    start = time.time()
    response = requests.get(url, headers=headers)
    print(f"Time: {time.time()-start:.2f}s | Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    reviews = soup.select('.review_list_new_item_block')
    print(f"Found {len(reviews)} reviews via requests")
    if reviews:
        print(reviews[0].text[:500].strip())

if __name__ == "__main__":
    test_requests_scraper()

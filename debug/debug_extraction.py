import requests
from bs4 import BeautifulSoup

def debug_extract():
    url = "https://www.booking.com/reviewlist.es.html?pagename=boutique-malinalli&cc1=mx&type=total&offset=0&rows=5"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'es-MX,es;q=0.9',
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    blocks = soup.select('.review_list_new_item_block')
    
    for i, block in enumerate(blocks):
        print(f"====== REVIEW {i} ======")
        for li in block.select('li'):
            print(f"  LI class: {li.get('class')} -> {repr(li.text.strip())}")
            
if __name__ == "__main__":
    debug_extract()

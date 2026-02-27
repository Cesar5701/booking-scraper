import requests
from bs4 import BeautifulSoup

def fetch_api_dom():
    url = "https://www.booking.com/reviewlist.es.html?pagename=boutique-malinalli&cc1=mx&type=total&offset=0&rows=20"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'es-MX,es;q=0.9',
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    blocks = soup.select('.review_list_new_item_block')
    for i, block in enumerate(blocks):
        # Todo el texto del bloque izquierdo (info del stay)
        left_panel_text = block.select('.review-panel-wide__item-info')
        if left_panel_text:
            for panel in left_panel_text:
                print(f"REVIEW {i} PANEL INFO: {panel.text.strip()}")
                
        # Buscar explícitamente todos los LI
        list_items = block.select('li')
        if list_items:
            print(f"REVIEW {i} LIST ITEMS:")
            for li in list_items:
                 print(f"  - {li.text.strip()}")

if __name__ == '__main__':
    fetch_api_dom()

import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, TypedDict
import time

from src.utils.cleaning import extract_score_from_text

class ReviewData(TypedDict):
    hotel_name: str
    hotel_url: str
    title: str
    score: str
    positive: str
    negative: str
    date: str
    room_type: str
    traveler_type: str
    nationality: str
    nights_stayed: str

class ReviewsModal:
    """
    Nuevo extractor ultra-rápido que utiliza el endpoint oculto de Booking.com
    para obtener HTML puro sin necesidad de Selenium renders.
    """
    def __init__(self, hotel_name: str, hotel_url: str):
        self.hotel_name = hotel_name
        self.hotel_url = hotel_url
        
        # Parsear el hotel_id desde la URL limpia para la API
        # Ejemplo: https://www.booking.com/hotel/mx/fiore-master-en-valquirico.es-mx.html -> fiore-master-en-valquirico
        try:
            self.hotel_id = hotel_url.split('/hotel/mx/')[1].split('.')[0]
        except Exception:
            self.hotel_id = ""
            
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'es-MX,es;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        }

    def _extract_review_data(self, review_elem) -> ReviewData:
        try:
            # Title
            title_elem = review_elem.select_one('.c-review-block__title')
            title = title_elem.text.strip() if title_elem else ""
            
            # Score
            score_elem = review_elem.select_one('.bui-review-score__badge')
            raw_score = score_elem.text.strip() if score_elem else ""
            score = extract_score_from_text(raw_score)
            
            # Positive & Negative text
            pos_elem = review_elem.select_one('.c-review__body--positive')
            pos = pos_elem.text.strip() if pos_elem else ""
            
            neg_elem = review_elem.select_one('.c-review__body--negative')
            neg = neg_elem.text.strip() if neg_elem else ""
            
            # Si no hay cajones separados
            if not pos and not neg:
                fallback_elem = review_elem.select_one('.c-review__body')
                if fallback_elem:
                    pos = fallback_elem.text.strip()
                    
            # Date fallback
            date_elem = review_elem.select_one('.c-review-block__date')
            date = date_elem.text.strip() if date_elem else ""
            
            # --- METADATA ---
            room_type = ""
            traveler_type = ""
            nationality = ""
            nights_stayed = ""
            
            # 1. Nacionalidad (Siempre bajo el nombre en un avatar block subtitle)
            metadata_spans = review_elem.select('.bui-avatar-block__subtitle')
            for span in metadata_spans:
                text = span.text.strip()
                if text:
                    # El primer span válido del User Block suele ser la nacionalidad del autor
                    nationality = text
                    break # Booking pone país en el primer subtitle
                    
            # 2. Detalles del Cuarto, Noches y Viajero (En una lista)
            list_items = review_elem.select('.bui-list__item')
            if not list_items:
                # Fallback genérico para algunos DOM styles
                list_items = review_elem.select('li')
                
            for li in list_items:
                # Ignorar posibles fotos o basura
                if 'c-review-block__photos__item' in li.get('class', []):
                    continue
                    
                text = li.text.strip()
                lower_text = text.lower()
                
                # Noches ("2 noches", "1 noche")
                if "noch" in lower_text:
                    nights_stayed = text.split('·')[0].strip()
                    
                # Viajero
                elif any(keyword in lower_text for keyword in ["viaj", "familia", "pareja", "grupo", "amig", "solo", "sola"]):
                    traveler_type = text
                    
                # Tipo de Habitación
                else:
                    # Si no es Noches y no es Viajero y no está vacío, generalmente es el cuarto
                    if text and not room_type:
                        room_type = text
                        
            return {
                "hotel_name": self.hotel_name, 
                "hotel_url": self.hotel_url, 
                "title": title, 
                "score": score,
                "positive": pos, 
                "negative": neg, 
                "date": date,
                "room_type": room_type,
                "traveler_type": traveler_type,
                "nationality": nationality,
                "nights_stayed": nights_stayed
            }
        except Exception as e:
            logging.warning(f"Failed to parse review HTML block: {e}")
            return {} # type: ignore

    def extract_all_reviews(self) -> List[ReviewData]:
        """
        Extrae todas las reseñas disponibles descargando HTML puro por offsets de página usando Requests.
        Ignora los límites de paginación o el lazy loading engañoso de Booking.
        """
        all_reviews = []
        offset = 0
        rows_per_page = 10
        consecutive_empty = 0
        
        if not self.hotel_id:
            logging.error(f"[ERROR] URL malformada, incapaz de idenfiticar hotel: {self.hotel_url}")
            return []
            
        logging.info(f"      [REQUESTS] Iniciando descarga API paralela para: {self.hotel_id}")
        
        # Paginación infinita hasta que Booking devuelva 0 reviews
        while True:
            # Endpoint interno de Booking para recargar el bloque de comentarios ajax
            url = f"https://www.booking.com/reviewlist.es.html?pagename={self.hotel_id}&cc1=mx&type=total&offset={offset}&rows={rows_per_page}"
            
            try:
                # Descargamos
                req_start = time.time()
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code != 200:
                    logging.warning(f"      [REQUESTS ERROR] Status {response.status_code} en offset {offset}")
                    break
                    
                # Parsear HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                review_blocks = soup.select('.review_list_new_item_block')
                
                # Criterio de parada
                if not review_blocks:
                    consecutive_empty += 1
                    if consecutive_empty >= 2: # Tolerancia de un salto fantasma
                        break
                else:
                    consecutive_empty = 0
                    
                # Transformar datos
                for block in review_blocks:
                    data = self._extract_review_data(block)
                    if data:
                        all_reviews.append(data)
                        
                logging.info(f"      [REQUESTS] Pág {(offset//10)+1} extraída ({len(review_blocks)} items) en {time.time()-req_start:.2f}s | Acumulado: {len(all_reviews)}")
                offset += rows_per_page
                
            except requests.RequestException as e:
                logging.error(f"      [REQUESTS CRASH] Error de red: {e}")
                break
                
        return all_reviews

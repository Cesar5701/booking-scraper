"""
Módulo de Extracción de Reseñas por API Interna (REST HTML)

Este módulo optimiza la descarga de información eludiendo el motor de renderización (DOM)
completo de Selenium. Transforma el sistema a un enfoque basado en HTTP Requests usando BeautifulSoup.
Interactúa con el endpoint no documentado utilizado asíncronamente por Ajax de Booking (`/reviewlist.es.html`).
"""
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
    Extractor enfocado en recuperar HTML puro mediante peticiones iterativas (offsets).
    Al imitar las cabeceras HTTP (Headers) correctas, el servidor devuelve un componente HTML conteniendo
    directamente los cajones textuales de cada huésped.
    """
    def __init__(self, hotel_name: str, hotel_url: str):
        self.hotel_name = hotel_name
        self.hotel_url = hotel_url
        
        # Parsear el identificador interno ('hotel_id') desde la URL estandarizada de Booking
        # Ejemplo de ruta: https://www.booking.com/hotel/mx/fiore-master-en-valquirico.es-mx.html
        # Resultado aislado de la máscara regex manual: 'fiore-master-en-valquirico'
        try:
            self.hotel_id = hotel_url.split('/hotel/mx/')[1].split('.')[0]
        except Exception:
            self.hotel_id = ""
            
        # Headers esenciales para que el Firewall de Application Routing no bloquée por falta de huella 
        # (Spoofing the User-Agent)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'es-MX,es;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        }

    def _extract_review_data(self, review_elem) -> ReviewData:
        """
        Analizador sintáctico especializado (Parser DOM Estático) con BeautifulSoup.
        Descompone el bloque individual (`.review_list_new_item_block`) extrayendo nodos clave de evaluación y demográficos.
        
        Args:
            review_elem (bs4.element.Tag): Nodo HTML con aislamiento de clase CSS de la reseña.
        """
        try:
            # 1. Recuperar Título Principal del Comentario
            title_elem = review_elem.select_one('.c-review-block__title')
            title = title_elem.text.strip() if title_elem else ""
            
            # 2. Recuperar Puntuación Numérica base 10 (Ej: "8,5") y normalizar
            score_elem = review_elem.select_one('.bui-review-score__badge')
            raw_score = score_elem.text.strip() if score_elem else ""
            score = extract_score_from_text(raw_score)
            
            # 3. Analizar Contenedores Bi-Lados Opcionales (Lo que me gustó / no me gustó)
            pos_elem = review_elem.select_one('.c-review__body--positive')
            pos = pos_elem.text.strip() if pos_elem else ""
            
            neg_elem = review_elem.select_one('.c-review__body--negative')
            neg = neg_elem.text.strip() if neg_elem else ""
            
            # Condicional de Estructura Clásica (Cuando solo hay 1 cajón de retroalimentación en vez de separación positiva/negativa)
            if not pos and not neg:
                fallback_elem = review_elem.select_one('.c-review__body')
                if fallback_elem:
                    pos = fallback_elem.text.strip()
                    
            # 4. Extraer la marca temporal de publicación
            date_elem = review_elem.select_one('.c-review-block__date')
            date = date_elem.text.strip() if date_elem else ""
            
            # --- SECCIÓN: METADATOS SOCIO-DEMOGRÁFICOS ---
            room_type = ""
            traveler_type = ""
            nationality = ""
            nights_stayed = ""
            
            # Parsear la Nacionalidad: Invariablemente ubicada debajo del nombre visible en bloque '.bui-avatar-block__subtitle'
            metadata_spans = review_elem.select('.bui-avatar-block__subtitle')
            for span in metadata_spans:
                text = span.text.strip()
                if text:
                    # El primer span válido alojado como subtítulo de bloque de avatar del usuario es un texto geográfico
                    nationality = text
                    break
                    
            # Parsear la Tipología del Viaje (Habitación, Noches, Grupo Social de Célula de viaje) iterando items de la lista UI
            list_items = review_elem.select('.bui-list__item')
            if not list_items:
                list_items = review_elem.select('li')
                
            for li in list_items:
                # Omitir metadatos multimedia basura (Miniaturas fotográficas) 
                if 'c-review-block__photos__item' in li.get('class', []):
                    continue
                    
                text = li.text.strip()
                lower_text = text.lower()
                
                # Clasificador de Duración de Estancia
                if "noch" in lower_text:
                    nights_stayed = text.split('·')[0].strip()
                    
                # Clasificador Predictivo sobre Composición Social (Keyword Matching)
                elif any(keyword in lower_text for keyword in ["viaj", "familia", "pareja", "grupo", "amig", "solo", "sola"]):
                    traveler_type = text
                    
                # Por descarta heurístico el nodo restante representa Categoría de la Habitación
                else:
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
        Bucle de descarga infinita. Construye sobre el modelo asimétrico paramétrico de la API (Paginación tipo 'Offset').
        Envía peticiones con un avance lineal (0, 10, 20...) hasta el cese total de devolución de nodos de reseña validado
        por una tolerancia sintomática a las anomalías de red.
        
        Returns:
            List[ReviewData]: Colección masiva en memoria de los diccionarios evaluativos extraídos.
        """
        all_reviews = []
        offset = 0
        rows_per_page = 10
        consecutive_empty = 0
        
        if not self.hotel_id:
            logging.error(f"[ERROR] URL malformada, incapaz de idenfiticar hotel: {self.hotel_url}")
            return []
            
        logging.info(f"      [REQUESTS] Iniciando descarga API paralela para: {self.hotel_id}")
        
        # Paginación controlada por comprobación recursiva de agotamiento de datos
        while True:
            # Endpoint interno inyectando Query Strings de parametrización (PageName y Offset Dinámico)
            url = f"https://www.booking.com/reviewlist.es.html?pagename={self.hotel_id}&cc1=mx&type=total&offset={offset}&rows={rows_per_page}"
            
            try:
                # Efectuar descarga de recursos
                req_start = time.time()
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code != 200:
                    logging.warning(f"      [REQUESTS ERROR] Status {response.status_code} en offset {offset}")
                    break
                    
                # Descompilar recurso estático en Árbol Abstracto de sintaxis BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                review_blocks = soup.select('.review_list_new_item_block')
                
                # Criterio de Freno Arquitectónico si Booking devuelva cero reseñas contiguas:
                # Puede ser ocasional (cero reseñas por error de motor base) -> permitiendo una tolerancia de '2 iteraciones (Saltos Fantasmas)'
                if not review_blocks:
                    consecutive_empty += 1
                    if consecutive_empty >= 2: 
                        break
                else:
                    consecutive_empty = 0
                    
                # Parsear el listado bloque a bloque e insertarlo en memoria estática
                for block in review_blocks:
                    data = self._extract_review_data(block)
                    if data:
                        all_reviews.append(data)
                        
                logging.info(f"      [REQUESTS] Pág {(offset//10)+1} extraída ({len(review_blocks)} items) en {time.time()-req_start:.2f}s | Acumulado: {len(all_reviews)}")
                
                # Iterar salto secuencial matemático
                offset += rows_per_page
                
            except requests.RequestException as e:
                logging.error(f"      [REQUESTS CRASH] Error de red intermitente interrumpiendo flujo: {e}")
                # En sistemas maduros requereríamos lógica de 'Rate Limiting / BackOff-Retry'. En caso de fallo forzamos salida para retener las extraídas previas
                break
                
        return all_reviews

import csv
import time
import os
import random
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

import config

# --- CONFIGURACIÓN DEL SCRAPER ---
# Usamos 'lang=es' para asegurar que la interfaz cargue en español
# Variables importadas de config.py


def initialize_driver():
    """Inicializa Chrome con opciones anti-detección y en español."""
    print("🚀 Iniciando WebDriver...")
    options = Options()
    if config.HEADLESS_MODE:
        options.add_argument("--headless=new")
    
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    
    # Configuración de idioma español
    options.add_argument("--lang=es-MX")
    options.add_experimental_option('prefs', {'intl.accept_languages': 'es-MX,es'})
    
    # User-Agent moderno para parecer un navegador real
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def save_reviews_batch(writer, data):
    """Guarda un lote de reseñas usando el writer abierto."""
    if not data: return
    writer.writerows(data)
    print(f"   💾 {len(data)} reseñas guardadas.")


def get_all_hotel_links(driver, url):
    """Fase 1: Obtener enlaces de todos los hoteles en la búsqueda."""
    print(f"🌍 Navegando a: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, config.MAX_WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="property-card"]'))
        )
    except TimeoutException:
        print("❌ Los resultados iniciales no cargaron. Abortando.")
        return []

    print("🔄 Cargando lista completa (Scroll + Botón 'Cargar más')...")
    scroll_attempts = 0
    max_attempts = 3
    
    while scroll_attempts < max_attempts:
        # Guardar número actual de elementos para comparar
        current_cards = len(driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]'))
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        try:
            # Esperar a que aparezca el botón o que cambie la altura/elementos
            # Selector bilingüe para el botón de cargar más
            load_more_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Load more') or contains(., 'Cargar más')]"))
            )
            driver.execute_script("arguments[0].click();", load_more_btn)
            print("   👉 Botón 'Cargar más' clickeado.")
            
            # Esperar a que carguen más elementos
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')) > current_cards
            )
            scroll_attempts = 0
        except TimeoutException:
            # Si no aparece botón, tal vez solo es scroll infinito o ya no hay más
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0 # Se movió, seguimos intentando
    
    print("\n🔍 Extrayendo enlaces finales...")
    elements = driver.find_elements(By.CSS_SELECTOR, 'a[data-testid="title-link"]')
    links = list(dict.fromkeys([e.get_attribute("href") for e in elements if e.get_attribute("href")]))
    
    print(f"🔗 TOTAL HOTELES ENCONTRADOS: {len(links)}")
    
    # Guardar respaldo de enlaces
    # Guardar respaldo de enlaces
    with open(config.LINKS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hotel_link"])
        for l in links: writer.writerow([l])
        
    return links


def _get_safe_text(element, selector):
    """Ayuda a extraer texto de forma segura sin romper el script."""
    try:
        return element.find_element(By.CSS_SELECTOR, selector).text.strip()
    except NoSuchElementException:
        return ""


def get_hotel_name_robust(driver):
    """
    Intenta extraer el nombre del hotel usando JSON-LD (metadatos ocultos)
    como prioridad, ya que los selectores CSS cambian constantemente.
    """
    # ESTRATEGIA 1: JSON-LD (Datos Estructurados - Muy Estable)
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            content = script.get_attribute("innerHTML")
            if "Hotel" in content or "LodgingBusiness" in content:
                data = json.loads(content)
                if isinstance(data, dict): data = [data]
                for item in data:
                    if item.get("@type") in ["Hotel", "LodgingBusiness", "Resort", "Hostel"]:
                        name = item.get("name")
                        if name: return name
    except: pass

    # ESTRATEGIA 2: Meta Tags OpenGraph
    try:
        og_title = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:title"]').get_attribute("content")
        if og_title: return og_title.split(",")[0].strip()
    except: pass

    # ESTRATEGIA 3: ID Clásico
    try:
        id_name = driver.find_element(By.ID, "hp_hotel_name").text.strip()
        if id_name: return id_name
    except: pass

    # ESTRATEGIA 4: Selectores Visuales (Fallback)
    visual_selectors = ['h2.pp-header__title', 'h2[data-testid="post-booking-header-title"]', '.hp__hotel-name']
    for sel in visual_selectors:
        txt = _get_safe_text(driver, sel)
        if txt: return txt

    # ESTRATEGIA 5: Título de la Pestaña
    try:
        return driver.title.split("Booking.com")[0].replace("Updated Prices", "").strip().rstrip("-").strip()
    except:
        return "Nombre_Desconocido"


def extract_reviews_from_hotel(driver, hotel_url):
    """Fase 2: Entrar al hotel, obtener nombre, abrir reseñas y paginar."""
    driver.get(hotel_url)
    
    # Esperar a que cargue el cuerpo de la página o el título
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        print("      ⚠️ Timeout cargando la página del hotel.")
        return []

    # 1. Obtener nombre robusto
    hotel_name = get_hotel_name_robust(driver)
    print(f"   🏨 Procesando: {hotel_name}")

    # 2. Intentar cerrar popups de login/cookies
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label*="Dismiss"], button[aria-label*="Ignorar"], button[aria-label*="Cerrar"]'))
        ).click()
    except: pass

    # 3. ABRIR PESTAÑA DE RESEÑAS
    print("      👉 Intentando abrir panel de reseñas...")
    reviews_opened = False
    
    # Lista de estrategias para abrir el panel
    open_strategies = [
        (By.CSS_SELECTOR, '[data-testid="review-score-link"]'), # El puntaje grande suele ser clicable
        (By.ID, "show_reviews_tab"),                           # ID clásico
        (By.CSS_SELECTOR, '[data-testid="guest-reviews-tab-trigger"]'),
        (By.PARTIAL_LINK_TEXT, "Comentarios"),
        (By.PARTIAL_LINK_TEXT, "Reviews"),
        (By.XPATH, "//a[contains(@href, '#tab-reviews')]")
    ]
    
    for by, selector in open_strategies:
        try:
            elem = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].click();", elem)
            # Esperar a que aparezca AL MENOS UNA reseña o el contenedor de lista
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="review"], .c-review-block, .review_list_new_item_block'))
            )
            reviews_opened = True
            print(f"      ✅ Panel abierto usando: {selector}")
            break
        except Exception:
            continue

    if not reviews_opened:
        print("   ⚠️ No se pudo abrir la pestaña de reseñas (o no hay reseñas).")
        return []

    # 4. EXTRACCIÓN Y PAGINACIÓN
    collected_reviews = []
    page = 1
    
    while True:
        # Esperar carga de reseñas en la página actual
        try:
            review_elements = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="review"], li.review_item, .c-review-block'))
            )
        except TimeoutException:
            print("      ⚠️ Tiempo de espera agotado buscando reseñas en esta página.")
            break

        print(f"      📄 Pág {page}: Encontrados {len(review_elements)} elementos.")
        
        initial_count = len(collected_reviews)
        
        for review in review_elements:
            try:
                # Extracción con selectores múltiples (fallback)
                title = _get_safe_text(review, '[data-testid="review-title"], .c-review-block__title')
                
                # Score
                raw_score = _get_safe_text(review, '[data-testid="review-score"], .bui-review-score__badge')

                # Limpiar el score: tomar solo la primera línea y reemplazar comas.
                if '\n' in raw_score:
                    score = raw_score.split('\n')[0]
                else:
                    score = raw_score
                
                score = score.replace("Score:", "").replace("Puntuación:", "").replace(",", ".").strip()
                
                # Texto Positivo/Negativo
                pos = _get_safe_text(review, '[data-testid="review-positive-text"], .c-review__body--positive')
                neg = _get_safe_text(review, '[data-testid="review-negative-text"], .c-review__body--negative')
                
                # Si no hay pos/neg separados, intentar buscar cuerpo general (raro en Booking, pero posible)
                if not pos and not neg:
                    body = _get_safe_text(review, '.c-review-block__row')
                    if body: pos = body # Guardamos en pos temporalmente

                # Fecha
                date = _get_safe_text(review, '[data-testid="review-date"], .c-review-block__date')

                data = {
                    "hotel_name": hotel_name, "hotel_url": hotel_url, 
                    "title": title, "score": score,
                    "positive": pos, "negative": neg, 
                    "date": date
                }
                
                if data not in collected_reviews:
                    collected_reviews.append(data)
            except StaleElementReferenceException:
                continue 
        
        # Verificar si extrajimos algo nuevo
        if len(collected_reviews) == initial_count:
            # A veces hay elementos vacíos o publicidad, intentamos una vez más avanzar
            pass

        # 5. IR A SIGUIENTE PÁGINA
        try:
            # Selector robusto para el botón "Siguiente"
            next_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="pagination-next-link"], button[aria-label="Next page"], button[aria-label="Página siguiente"]'))
            )
            
            # Capturar el primer elemento de reseña actual para detectar cuando cambie la página (stale)
            current_first_review = review_elements[0] if review_elements else None
            
            driver.execute_script("arguments[0].click();", next_btn)
            
            # Esperar a que la lista de reseñas se actualice (stale element reference es buena señal de recarga)
            if current_first_review:
                WebDriverWait(driver, 10).until(
                    EC.staleness_of(current_first_review)
                )
            
            # Esperar a que aparezcan las nuevas reseñas
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="review"], li.review_item, .c-review-block'))
            )
            
            page += 1
        except (TimeoutException, NoSuchElementException):
            print("      🏁 Fin de la paginación (no se detectó botón 'Siguiente' o no cargó siguiente página).")
            break 
        except Exception as e:
            print(f"      ❌ Error al intentar cambiar de página: {e}")
            break

    return collected_reviews


def main():
    # Lógica de Reanudación
    processed_urls = set()
    if os.path.isfile(config.RAW_REVIEWS_FILE):
        try:
            df = pd.read_csv(config.RAW_REVIEWS_FILE)
            processed_urls = set(df['hotel_url'].unique())
            print(f"✅ Lógica de reanudación activada. {len(processed_urls)} hoteles ya procesados.")
        except (pd.errors.EmptyDataError, KeyError):
             print(f"⚠️ Archivo de reseñas vacío o inválido. Iniciando desde cero.")
             pass

    driver = initialize_driver()
    
    try:
        links = get_all_hotel_links(driver, config.SEARCH_URL)
        
        if not links:
            print("🛑 No se encontraron hoteles.")
            return

        if config.HOTEL_VISIT_LIMIT > 0:
            print(f"\n⚠️ MODO PRUEBA: Procesando solo los primeros {config.HOTEL_VISIT_LIMIT} hoteles.")
            links_to_process = links[:config.HOTEL_VISIT_LIMIT]
        else:
            print(f"\n🚀 MODO COMPLETO: Procesando todos los {len(links)} hoteles encontrados.")
            links_to_process = links

        review_headers = ["hotel_name", "hotel_url", "title", "score", "positive", "negative", "date"]
        total = len(links_to_process)
        
        # Abrir archivo una sola vez
        # Abrir archivo una sola vez
        file_exists = os.path.isfile(config.RAW_REVIEWS_FILE)
        with open(config.RAW_REVIEWS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=review_headers)
            if not file_exists:
                writer.writeheader()
                
            for i, link in enumerate(links_to_process):
                if link in processed_urls:
                    print(f"⏭️ ({i+1}/{total}) Saltando hotel ya procesado: {link}")
                    continue

                print(f"\n🏨 ({i+1}/{total}) Procesando enlace: {link}")
                
                try:
                    reviews = extract_reviews_from_hotel(driver, link)
                    if reviews:
                        print(f"   ✅ Extraídas {len(reviews)} reseñas en total.")
                        save_reviews_batch(writer, reviews)
                        f.flush() # Asegurar escritura en disco
                    else:
                        print("   ℹ️ No se capturaron reseñas.")
                except Exception as e:
                    print(f"   ❌ Error crítico en este hotel: {e}")

    finally:
        print("\n🏁 Proceso finalizado. Cerrando navegador.")
        driver.quit()

if __name__ == "__main__":
    main()
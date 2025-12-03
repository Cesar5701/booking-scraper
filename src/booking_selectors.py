from selenium.webdriver.common.by import By

class SearchResults:
    PROPERTY_CARD = (By.CSS_SELECTOR, '[data-testid="property-card"]')
    LOAD_MORE_BUTTON = (By.XPATH, "//button[contains(., 'Load more') or contains(., 'Cargar más')]")
    
    # Selectores para enlaces de hoteles (lista de posibles candidatos)
    HOTEL_LINKS = 'a.e3859ef1a4, a[data-testid="title-link"], a[data-testid="property-card-desktop-single-image"], .c-property-card__title a'

class HotelPage:
    # Estrategias para obtener el nombre del hotel
    NAME_JSON_LD = (By.XPATH, "//script[@type='application/ld+json']")
    NAME_OG_TITLE = (By.CSS_SELECTOR, 'meta[property="og:title"]')
    NAME_ID = (By.ID, "hp_hotel_name")
    
    # Selectores visuales de respaldo para el nombre (CSS)
    NAME_VISUAL_SELECTORS = [
        'h2.pp-header__title', 
        'h2[data-testid="post-booking-header-title"]', 
        '.hp__hotel-name'
    ]
    
    # Conteo de reseñas
    REVIEW_COUNT_LINKS = '[data-testid="review-score-link"], .js-review-tab-link, [data-tab-target="htReviews"]'
    REVIEW_COUNT_SIDEBAR = '.bui-review-score__text, .d8eab2cf7f'
    
    # Popups
    LOGIN_POPUP_CLOSE = 'button[aria-label*="Dismiss"], button[aria-label*="Ignorar"], button[aria-label*="Cerrar"]'
    
    # Google One Tap
    GOOGLE_ONE_TAP_IFRAME = "iframe[id*='credential_picker']"
    GOOGLE_ONE_TAP_CLOSE = "#close"
    
    # Estrategias para abrir la pestaña de reseñas (Tuplas By, Selector)
    OPEN_REVIEWS_STRATEGIES = [
        (By.CSS_SELECTOR, '[data-testid="review-score-link"]'),
        (By.CSS_SELECTOR, '[data-testid="review-score-component"]'),
        (By.CSS_SELECTOR, '.js-review-tab-link'),
        (By.CSS_SELECTOR, '[data-tab-target="htReviews"]'),
        (By.ID, "show_reviews_tab"),
        (By.CSS_SELECTOR, '[data-testid="guest-reviews-tab-trigger"]'),
        (By.PARTIAL_LINK_TEXT, "Comentarios"),
        (By.PARTIAL_LINK_TEXT, "Reviews"),
        (By.XPATH, "//a[contains(@href, '#tab-reviews')]")
    ]

class Reviews:
    # Contenedores de reseñas
    ITEM = '[data-testid="review"], li.review_item, .c-review-block'
    
    # Elementos internos de una reseña (CSS)
    TITLE = '[data-testid="review-title"], .c-review-block__title'
    SCORE = '[data-testid="review-score"], .bui-review-score__badge'
    POSITIVE = '[data-testid="review-positive-text"], .c-review__body--positive'
    NEGATIVE = '[data-testid="review-negative-text"], .c-review__body--negative'
    BODY_FALLBACK = '.c-review-block__row'
    DATE = '[data-testid="review-date"], .c-review-block__date'
    
    # Paginación
    NEXT_PAGE = '[data-testid="pagination-next-link"], button[aria-label="Next page"], button[aria-label="Página siguiente"]'

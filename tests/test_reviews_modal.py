import pytest
from unittest.mock import MagicMock
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from src.pages.reviews_modal import ReviewsModal
from src.booking_selectors import Reviews

# HTML Fixture simulado (simplificado)
MOCK_HTML = """
<div data-testid="review" class="c-review-block">
    <div data-testid="review-title" class="c-review-block__title">Excelente estancia</div>
    <div data-testid="review-score" class="bui-review-score__badge">9.5</div>
    <div data-testid="review-date" class="c-review-block__date">Reviewed: 20 Oct 2023</div>
    <div data-testid="review-positive-text" class="c-review__body--positive">Todo muy limpio y ordenado.</div>
    <div data-testid="review-negative-text" class="c-review__body--negative">Nada que objetar.</div>
</div>
<div data-testid="review" class="c-review-block">
    <div data-testid="review-title" class="c-review-block__title">Malo</div>
    <div data-testid="review-score" class="bui-review-score__badge">4,0</div>
    <div data-testid="review-date" class="c-review-block__date">Reviewed: 10 Jan 2023</div>
    <div class="c-review-block__row">No me gustó el ruido.</div>
</div>
"""

@pytest.fixture
def mock_driver():
    driver = MagicMock()
    return driver

@pytest.fixture
def reviews_modal(mock_driver):
    return ReviewsModal(mock_driver, "Test Hotel", "http://test.com")

def test_extract_current_page(reviews_modal, mock_driver):
    # Mock de find_elements para devolver mocks de WebElements
    # Simulamos 2 elementos de reseña
    elem1 = MagicMock(spec=WebElement)
    elem2 = MagicMock(spec=WebElement)
    
    # Configurar el comportamiento de find_element dentro de _extract_review_data
    # Esto es un poco complejo de mockear perfectamente con Selenium puro, 
    # pero simularemos el comportamiento de _get_safe_text
    
    def get_text_side_effect(element, selector):
        # Simulación simple basada en el elemento y selector
        if element == elem1:
            if selector == Reviews.TITLE: return "Excelente estancia"
            if selector == Reviews.SCORE: return "9.5"
            if selector == Reviews.POSITIVE: return "Todo muy limpio y ordenado."
            if selector == Reviews.NEGATIVE: return "Nada que objetar."
            if selector == Reviews.DATE: return "Reviewed: 20 Oct 2023"
        elif element == elem2:
            if selector == Reviews.TITLE: return "Malo"
            if selector == Reviews.SCORE: return "4,0"
            if selector == Reviews.POSITIVE: return "" # Simular elemento no encontrado (safe text devuelve "")
            if selector == Reviews.NEGATIVE: return ""
            if selector == Reviews.BODY_FALLBACK: return "No me gustó el ruido."
            if selector == Reviews.DATE: return "Reviewed: 10 Jan 2023"
        return ""

    # Monkeypatching _get_safe_text para evitar mockear toda la estructura de Selenium
    # Esto prueba la lógica de extracción y estructuración, no Selenium en sí.
    reviews_modal._get_safe_text = MagicMock(side_effect=get_text_side_effect)
    
    # Mockear find_elements para devolver nuestra lista
    mock_driver.find_elements.return_value = [elem1, elem2]
    
    # Ejecutar
    reviews = reviews_modal.extract_current_page()
    
    # Verificaciones
    assert len(reviews) == 2
    
    r1 = reviews[0]
    assert r1['title'] == "Excelente estancia"
    assert r1['score'] == "9.5"
    assert r1['positive'] == "Todo muy limpio y ordenado."
    assert r1['negative'] == "Nada que objetar."
    
    r2 = reviews[1]
    assert r2['title'] == "Malo"
    assert r2['score'] == "4.0" # extract_score_from_text convierte "4,0" a "4.0"
    assert r2['positive'] == "No me gustó el ruido." # Fallback body
    assert r2['negative'] == ""

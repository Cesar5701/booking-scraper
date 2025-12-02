import pytest
import math
from src.utils.cleaning import clean_text_basic, fix_score_value

# --- Test clean_text_basic ---

def test_clean_text_basic_simple():
    assert clean_text_basic("  HOLA   Mundo  ") == "hola mundo"

def test_clean_text_basic_none():
    assert clean_text_basic(None) == ""

def test_clean_text_basic_number():
    assert clean_text_basic(123) == ""

def test_clean_text_basic_special_chars():
    assert clean_text_basic("¡Hola! ¿Qué tal?") == "¡hola! ¿qué tal?"

# --- Test fix_score_value ---

def test_fix_score_valid():
    assert fix_score_value("9.5") == 9.5
    assert fix_score_value(8) == 8.0
    assert fix_score_value("10") == 10.0

def test_fix_score_comma():
    assert fix_score_value("9,5") == 9.5

def test_fix_score_concatenation_error():
    # Caso crítico: 10 + 10 = 1010
    assert fix_score_value(1010) == 10.0
    # Caso: 9.5 + 9.5 = 95 (si se pierde el punto, aunque la lógica actual maneja >10 y <100)
    assert fix_score_value(95) == 9.5

def test_fix_score_invalid():
    assert fix_score_value(None) is None
    assert fix_score_value("abc") is None
    assert fix_score_value("") is None

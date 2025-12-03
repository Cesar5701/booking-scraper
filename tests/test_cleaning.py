import pytest
import math
from src.utils.cleaning import clean_text_basic, fix_score_value, extract_score_from_text

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



def test_fix_score_invalid():
    assert fix_score_value(None) is None
    assert fix_score_value("abc") is None
    assert fix_score_value("") is None

# --- Test extract_score_from_text ---

def test_extract_score_simple():
    assert extract_score_from_text("Score: 8.5") == "8.5"
    assert extract_score_from_text("10") == "10"
    assert extract_score_from_text("9,2") == "9.2"

def test_extract_score_complex():
    assert extract_score_from_text("Puntuación: 7.5 / 10") == "7.5"
    assert extract_score_from_text("Review score: 10") == "10"
    assert extract_score_from_text("Garbage text 5.0 more text") == "5.0"
    
def test_extract_score_invalid():
    assert extract_score_from_text("No score here") == "0"
    assert extract_score_from_text("") == "0"
    assert extract_score_from_text(None) == "0"

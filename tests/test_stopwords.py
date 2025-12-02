from src.utils.stopwords import get_stopwords

def test_get_stopwords():
    sw = get_stopwords()
    assert isinstance(sw, set)
    assert len(sw) > 0
    # Verificar palabras clave
    assert "hotel" in sw
    assert "the" in sw # Inglés
    assert "de" in sw # Español

import re
import pandas as pd
from typing import Optional, Union

# Compiled Regex Patterns
RE_SPACES = re.compile(r'\s+')
RE_LINEBREAKS = re.compile(r'[\r\n]+')
RE_SCORE_VAL = re.compile(r'(\d+(\.\d+)?)')
RE_SCORE_TEXT = re.compile(r'(\d+[\.,]?\d*)')

EMPTY_COMMENT_MARKER = "esta entrada no tiene comentarios"


def clean_text_basic(text: Union[str, float, None]) -> str:
    """
    Realiza una limpieza básica de texto para preprocesamiento.
    
    Args:
        text: El texto de entrada (puede ser str, float/NaN o None).
        
    Returns:
        str: Texto en minúsculas y sin espacios extra, o cadena vacía si la entrada no es válida.
    """
    if not isinstance(text, str):
        return ""
    # Convertir a minúsculas
    text = text.lower()
    # Eliminar espacios extra
    text = RE_SPACES.sub(' ', text).strip()
    return text


def build_clean_review_text(
    positive: Union[str, float, None],
    negative: Union[str, float, None],
    include_title: Union[str, float, None] = None,
) -> str:
    """
    Construye el texto limpio de una reseña filtrando el marcador predeterminado
    de Booking ('Esta entrada no tiene comentarios') y separando cláusulas
    opuestas o saltos de línea con puntuación explícita ('. ').
    """
    parts = []
    for raw_field in (include_title, positive, negative):
        if not isinstance(raw_field, str):
            continue
        # Reemplazar saltos de carro internos (\r, \n) por punto seguido cuando no terminen en puntuación
        segments = [seg.strip() for seg in RE_LINEBREAKS.split(raw_field) if seg.strip()]
        cleaned_segments = []
        for seg in segments:
            if EMPTY_COMMENT_MARKER in seg.lower():
                continue
            cleaned_segments.append(seg)
        if cleaned_segments:
            joined = ". ".join(
                s if s[-1] in ".!?;:" else f"{s}." for s in cleaned_segments
            )
            parts.append(joined)
    if not parts:
        return ""
    return clean_text_basic(" ".join(parts))

def fix_score_value(val: Union[str, float, int, None]) -> Optional[float]:
    """
    Limpia y normaliza el puntaje de una reseña.
    Maneja casos extremos como '1010' que ocurren por concatenación errónea en el scraping.
    
    Args:
        val: El valor del puntaje (str, número o None).
        
    Returns:
        float: El puntaje normalizado (0-10) o None si no es válido.
    """
    if pd.isna(val): return None
    s = str(val).replace(',', '.').strip()
    match = RE_SCORE_VAL.search(s)
    if match:
        try:
            num = float(match.group(1))
            # Normalizar si es mayor a 10 (ej. escala 100)
            if num > 10:
                if 10 < num <= 100: return num / 10
            return num
        except ValueError: return None
    return None

def extract_score_from_text(raw_score: str) -> str:
    """
    Extrae el primer número válido de una cadena de texto (ej. 'Score: 8.5' -> '8.5').
    Usa regex para ser robusto ante texto basura.
    """
    if not isinstance(raw_score, str):
        return "0"
        
    # Reemplazar comas por puntos para estandarizar
    cleaned = raw_score.replace(',', '.')
    
    match = RE_SCORE_TEXT.search(cleaned)
    if match:
        return match.group(1)
    return "0"

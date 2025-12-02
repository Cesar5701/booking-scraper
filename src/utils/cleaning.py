import re
import pandas as pd
from typing import Optional, Union

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
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
    match = re.search(r'(\d+(\.\d+)?)', s)
    if match:
        try:
            num = float(match.group(1))
            # Corrección heurística para errores de concatenación (ej. 10 + 10 = 1010)
            if num > 10:
                if num == 1010: return 10.0
                if 10 < num < 100: return num / 10
            return num
        except ValueError: return None
    return None

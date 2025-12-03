import logging
import os

def setup_logging(log_file: str = "scraper.log", level=logging.INFO):
    """
    Configura el logging globalmente para la aplicación.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True # Asegura que se reconfigure si ya se llamó antes
    )

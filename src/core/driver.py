import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

import config

def initialize_driver():
    """
    Inicializa Chrome con opciones anti-detección, idioma español y rotación de User-Agent.
    """
    logging.info("🚀 Iniciando WebDriver (Core)...")
    options = Options()
    
    if config.HEADLESS_MODE:
        options.add_argument("--headless=new")
    
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    
    # Configuración de idioma español
    options.add_argument("--lang=es-MX")
    options.add_experimental_option('prefs', {'intl.accept_languages': 'es-MX,es'})
    
    # User-Agent Rotativo
    try:
        ua = UserAgent()
        user_agent = ua.random
        logging.info(f"🎭 User-Agent asignado: {user_agent}")
    except Exception as e:
        logging.warning(f"⚠️ Falló fake-useragent ({e}), usando default.")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    options.add_argument(f"user-agent={user_agent}")
    
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Opciones adicionales para estabilidad
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

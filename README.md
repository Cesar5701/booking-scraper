# Booking.com Scraper

Este proyecto es un scraper robusto y modular para extraer reseñas de hoteles de Booking.com. Utiliza Selenium para la navegación y extracción de datos, y SQLAlchemy para la persistencia en una base de datos SQLite.

## Características

*   **Extracción Paralela**: Utiliza un modelo Productor-Consumidor con hilos para extraer reseñas de múltiples hoteles simultáneamente.
*   **Resiliencia**: Manejo robusto de errores, reintentos automáticos para elementos dinámicos (StaleElementReferenceException) y capacidad de reanudar trabajos interrumpidos.
*   **Deduplicación**: Sistema de hashing para evitar almacenar reseñas duplicadas en la base de datos y CSV.
*   **Análisis de Sentimientos**: Módulo de inferencia integrado (`src/inference.py`) que utiliza modelos de `pysentimiento` para clasificar reseñas (Positivo, Negativo, Neutro) en español e inglés.
*   **Clean Data**: Scripts utilitarios para limpieza y exportación de datos.

## Estructura del Proyecto

```
booking-scraper/
├── data/                   # Almacenamiento de datos (DB, CSV)
├── src/
│   ├── core/               # Lógica central (driver, pipeline, db)
│   ├── pages/              # Page Objects (modelado de páginas web)
│   ├── utils/              # Utilidades (limpieza, logging, idioma)
│   ├── config.py           # Configuración global
│   ├── models.py           # Modelos de base de datos (SQLAlchemy)
│   ├── scraper.py          # Script principal de scraping
│   ├── inference.py        # Script de análisis de sentimientos
│   └── ...
├── tests/                  # Tests unitarios
├── scraper_env/            # Entorno virtual
└── requirements.txt        # Dependencias
```

32: ## Instalación
33: 
34: 1.  Clonar el repositorio.
35: 2.  Crear y activar un entorno virtual:
36:     ```bash
37:     python3.11 -m venv scraper_venv
38:     source scraper_venv/bin/activate
39:     ```
40: 3.  Instalar dependencias:
41:     ```bash
42:     pip install -r requirements.txt
43:     ```
44: 
45: ## Uso
46: 
47: ### Scraping
48: Para iniciar el scraper:
49: ```bash
50: python -m src.scraper
51: ```
52: El scraper buscará hoteles definidos en la configuración, extraerá sus reseñas y las guardará en `data/reviews.db` y `data/tlaxcala_hotel_reviews_full.csv`.
53: 
54: ### Inferencia (Análisis de Sentimientos)
55: Para ejecutar el análisis de sentimientos sobre las reseñas guardadas:
56: ```bash
57: python -m src.inference
58: ```
59: 
60: ### Dashboard
61: Para visualizar los datos:
62: ```bash
63: streamlit run src/ui/dashboard.py
64: ```
65: 
66: ## Configuración
67: La configuración global se encuentra en `src/config.py`. Aquí puedes ajustar:
68: *   URLs de búsqueda.
69: *   Rutas de archivos de salida.
70: *   Configuración del navegador (Headless, User-Agent).
71: *   Parámetros de concurrencia (Número de hilos).
72: 
73: ## Tests
74: Para ejecutar los tests:
75: ```bash
76: pytest tests/
77: ```

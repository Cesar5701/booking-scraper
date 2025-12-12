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

## Instalación

1.  Clonar el repositorio.
2.  Crear y activar un entorno virtual:
    ```bash
    python3.11 -m venv scraper_venv
    source scraper_venv/bin/activate
    ```
3.  Instalar dependencias:
    ```bash
    pip install -r requirements.txt
    ```

## Uso

### Scraping
Para iniciar el scraper:
```bash
python -m src.scraper
```
El scraper buscará hoteles definidos en la configuración, extraerá sus reseñas y las guardará en `data/reviews.db` y `data/tlaxcala_hotel_reviews_full.csv`.

### Inferencia (Análisis de Sentimientos)
Para ejecutar el análisis de sentimientos sobre las reseñas guardadas:
```bash
python -m src.inference
```

### Dashboard
Para visualizar los datos:
```bash
streamlit run src/ui/dashboard.py
```

## Configuración
La configuración global se encuentra en `src/config.py`. Aquí puedes ajustar:
*   URLs de búsqueda.
*   Rutas de archivos de salida.
*   Configuración del navegador (Headless, User-Agent).
*   Parámetros de concurrencia (Número de hilos).

## Tests
Para ejecutar los tests:
```bash
pytest tests/
```

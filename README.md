# Booking.com Scraper & NLP Analysis Pipeline

Este proyecto es un sistema robusto, modular y de alto rendimiento para extraer reseñas de hoteles desde Booking.com, procesarlas con un pipeline avanzado de NLP (Procesamiento de Lenguaje Natural) para análisis de sentimientos, y prepararlas para visualización.

Recientemente actualizado, emplea una arquitectura híbrida para maximizar la recolección de datos y la velocidad extrema.

## Características Principales

*   **Arquitectura Híbrida de Scraping**: 
    *   **Fase 1 (Selenium)**: Navega dinámicamente el catálogo de hoteles para obtener URLs base.
    *   **Fase 2 (HTTP Requests & BeautifulSoup)**: Extrae reseñas paralelamente consumiendo directamente la API interna de Booking. Es capaz de descargar miles de reseñas en segundos, evadiendo los problemas de *Lazy Loading* y las demoras de renderización de navegadores gráficos.
*   **Extracción de Metadatos Ocultos**: Identifica y extrae directamente el **Tipo de Habitación** (`room_type`), **Tipo de Viajero** (`traveler_type`), **Noches de Estancia** (`nights_stayed`) y **Nacionalidad** (`nationality`).
*   **Deduplicación Robusta a nivel BD**: Utiliza "huellas digitales" (Unique Hashes) que limpian *tracking tokens* dinámicos de URLs para garantizar que la base de datos de SQLite jamás guarde reseñas duplicadas, incluso en corridas inter-semanales.
*   **Análisis de Sentimientos mediante GPU/CPU**: Módulo de inferencia integrado (`src/inference.py`) impulsado por `pysentimiento` y el modelo `RoBERTuito` para clasificar texto en español explícitamente en Probabilidades: Positivo, Negativo, Neutro.
*   **Resiliencia y Check-pointing**: El scraper guarda el progreso. Si la ejecución se detiene, continuará desde el último hotel guardado sin perder datos valiosos.
*   **Logs y Tiempos de Ejecución**: Monitoreo claro de cuantas reseñas procesa cada worker por segundo.

## Estructura del Proyecto

```text
booking-scraper/
├── data/                   # Base de Datos (reviews.db) y Exportaciones CSV
├── src/
│   ├── core/               # Lógica central: Manejo de hilos, Drivers y Pipeline de DB
│   ├── pages/              # Clases API (Ej: ReviewsModal con peticiones directas HTTP)
│   ├── utils/              # Funciones de limpieza y normalización
│   ├── config.py           # Configuración Global (Cabeceras CSV, # de workers, rutas)
│   ├── models.py           # Esquema SQLAlchemy (Tabla 'reviews')
│   ├── scraper.py          # Script principal de Scraping
│   ├── inference.py        # Script de Análisis de Sentimientos Computacional
│   └── ...
├── tests/                  # Tests unitarios 
├── scraper_venv/           # Entorno virtual
└── requirements.txt        # Dependencias
```

## Instalación y Configuración

1.  Clonar el repositorio.
2.  Crear y activar el entorno virtual (usando la versión de Python recomendada, ej. `3.11`):
    ```bash
    python3 -m venv scraper_venv
    source scraper_venv/bin/activate
    ```
3.  Instalar dependencias:
    ```bash
    pip install -r requirements.txt
    ```

## Uso y Comandos de Ejecución

> **Importante**: Ya que el proyecto emplea estructuras modulares bajo el directorio `src/`, se recomienda ejecutar los scripts siempre referenciando el path actual con variables de entorno si se invoca desde la raíz.

### 1. Scraping (Recolección de Reseñas pura)
Para iniciar la fase de recolección web híbrida hacia la Base de Datos y el CSV en crudo:
```bash
PYTHONPATH=. scraper_venv/bin/python src/scraper.py
```
*El scraper buscará los hoteles indexados en `config.py`, extraerá todas sus reseñas disponibles, y las persistirá de manera transaccional a SQLite impidiendo duplicados.*

### 2. Inferencia (Análisis de Sentimientos NLP)
Para ejecutar el Análisis de Deep Learning sobre las reseñas recién guardadas que aún no tengan puntajes de sentimiento calculados:
```bash
PYTHONPATH=. scraper_venv/bin/python src/inference.py
```
*El script detectará automáticamente el idioma de los nuevos renglones con FastText, y utilizará un modelo Transformer de redes neuronales (RoBERTuito) para predecir su polaridad.*

### 3. Interfaz Visual (Dashboard)
Para inicializar el tablero de control de Streamlit con los datos combinados:
```bash
PYTHONPATH=. scraper_venv/bin/streamlit run src/ui/dashboard.py
```

## Configuración Personalizable
Ajustando el archivo `src/config.py` podrás re-parametrizar el proyecto a tu escala:
*   URL de la zona geográfica central de los hoteles.
*   `MAX_WORKERS`: Límite de conexiones lógicas concurrentes hacia Booking (HTTP requests).
*   Rutas relativas de la base de datos o ubicaciones de exportación CSV.

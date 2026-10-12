# De la Voz del Viajero a la Predicción: Opiniones Turísticas Analizadas con Aprendizaje Profundo

Repositorio oficial del sistema computacional y protocolo experimental de la tesis de licenciatura en Ciencias de la Computación (BUAP). Desarrolla un pipeline integral para extraer, depurar, ajustar mediante *fine-tuning* (`RoBERTuito`) y visualizar opiniones digitales sobre servicios de hospedaje en el estado de Tlaxcala, México.

## Características Principales

*   **Arquitectura Híbrida de Scraping (`src/scraper.py`, `src/pages/reviews_modal.py`, `src/core/pipeline.py`)**: 
    *   **Fase 1 (Selenium POM)**: Navega dinámicamente el catálogo de establecimientos para descubrir URLs base.
    *   **Fase 2 (HTTP Requests + BeautifulSoup + Cola Productor-Consumidor)**: Descarga reseñas paginadas consumiendo el endpoint interno `/reviewlist.es.html` de Booking.com y persiste transaccionalmente en SQLite (`data/reviews.db`) con deduplicación MD5 (`review_hash`).
*   **Preprocesamiento Conservador y Control de Sesgos (`src/utils/cleaning.py`)**:
    *   Excluye marcadores vacíos generados por la plataforma (`"Esta entrada no tiene comentarios"`, $2,501$ casos) mediante `build_clean_review_text`.
    *   Separa sintácticamente los bloques positivo y negativo con puntuación explícita (`. `) y controla la fuga de etiquetas (*Target Leakage*) originada por títulos autogenerados (*"Excepcional"*, *"Fantástico"*, *"Muy bien"*, *"Bien"*, *"Agradable"*).
*   **Ajuste Fino Supervisado (*Fine-Tuning*) y Evaluación Estadística (`scripts/finetune_and_evaluate.py`)**:
    *   Ejecuta el *fine-tuning* supervisado de `RoBERTuito` (`pysentimiento/robertuito-sentiment-analysis`) en GPU con precisión mixta `FP16`, `AdamW` y pérdida de entropía cruzada ponderada sobre reseñas en español mexicano ($N=5,659$ cuerpos únicos).
    *   Compara contra *baselines* (`DummyClassifier`, `LogisticRegression`, `LinearSVC` con TF-IDF y `RoBERTuito Base`) reportando **Intervalos de Confianza Bootstrap al 95% ($B=1,000$)**, **prueba pareada de McNemar ($\chi^2$)**, partición agrupada por hotel (`GroupShuffleSplit`) y evaluación sobre la muestra aleatoria estratificada de validación lingüística ($n=200$, `data/validacion_humana_200.csv`).
*   **Inferencia Neuronal Bilingüe por Lotes (`src/inference.py`)**:
    *   Detecta el idioma con `FastText` (`lid.176.ftz`) y enruta las reseñas en español (`batch_es`, turistas nacionales e internacionales hispanohablantes) hacia `RoBERTuito` y las reseñas en inglés (`batch_en`, turistas extranjeros angloparlantes) hacia `BERTweet`, procesando en sub-lotes en GPU (`predict_in_batches`).
*   **Dashboard de Inteligencia Turística en Español (`src/ui/dashboard.py`)**:
    *   Construido en `Streamlit` y `Plotly Express` con 8 módulos interactivos en español: Ranking por **Índice de Satisfacción del Turista (TSI)** con suavizado bayesiano ($C=5$), Análisis de Sentimiento, Perfil del Turista, Mapa de Calor Demográfico (sin imputación artificial de ceros), Consistencia Calificación vs. Sentimiento, Matriz de Controversia Hotelera ($v_h \ge 10$), Nubes de Palabras (preservando sustantivos de aspectos en `src/utils/stopwords.py`) y Explorador de Reseñas.

## Estructura del Proyecto

```text
booking-scraper/
├── data/
│   ├── reviews.db                      # Base de datos SQLite (9,839 reseñas extraídas; 7,338 con texto válido)
│   └── validacion_humana_200.csv       # Muestra aleatoria estratificada (n=200) de validación lingüística
├── scripts/
│   ├── finetune_and_evaluate.py        # Fine-tuning en GPU, Bootstrap IC 95%, McNemar y GroupSplit
│   └── run_baseline.py                 # Script de contraste de regímenes con/sin título
├── src/
│   ├── core/                           # Concurrencia Productor-Consumidor, Driver y sesión SQLAlchemy
│   ├── pages/                          # POM y extractor HTTP asíncrono (ReviewsModal)
│   ├── ui/
│   │   └── dashboard.py                # Tablero interactivo Streamlit + Plotly (100% en español)
│   ├── utils/                          # Limpieza (build_clean_review_text), FastText y Stopwords
│   ├── config.py                       # Configuración global
│   ├── models.py                       # Esquema ORM SQLAlchemy (Tabla 'reviews')
│   ├── scraper.py                      # Orquestador de extracción en 2 fases
│   └── inference.py                    # Orquestador de inferencia neuronal bilingüe por lotes
├── tesis/                              # Código fuente LaTeX, figuras vectoriales y main.pdf compilado
├── tests/                              # Suite de pruebas unitarias
└── requirements.txt                    # Dependencias del proyecto
```

## Instalación y Configuración

1.  Clonar el repositorio y crear el entorno virtual (Python 3.11+):
    ```bash
    python3 -m venv scraper_venv
    source scraper_venv/bin/activate
    pip install -r requirements.txt
    ```

## Uso y Comandos de Ejecución

### 1. Extracción de Reseñas (Scraper)
```bash
PYTHONPATH=. scraper_venv/bin/python src/scraper.py
```

### 2. Inferencia Neuronal en Base de Datos (GPU / CPU)
```bash
PYTHONPATH=. scraper_venv/bin/python src/inference.py
```

### 3. Ajuste Fino Supervisado (`Fine-Tuning`) y Evaluación Estadística
Reproduce las métricas del Capítulo 6 (`tesis/figuras/experimental_results.json` y matrices de confusión):
```bash
PYTHONPATH=. scraper_venv/bin/python scripts/finetune_and_evaluate.py
```

### 4. Dashboard Interactivo (Streamlit)
```bash
PYTHONPATH=. scraper_venv/bin/streamlit run src/ui/dashboard.py
```

### 5. Ejecución de Pruebas Unitarias
```bash
PYTHONPATH=. scraper_venv/bin/python -m unittest tests/test_cleaning.py tests/test_stopwords.py tests/test_inference.py
```

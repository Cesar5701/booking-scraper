# Booking.com Hotel Review Scraper

Este es un scraper avanzado de Python diseñado para extraer de manera eficiente y robusta datos de hoteles y todas sus reseñas desde Booking.com.

## Características Principales

- **Extracción Completa**: Navega por las páginas de búsqueda, obtiene los enlaces de los hoteles y luego visita cada uno para extraer **todas** las reseñas paginando hasta el final.
- **Datos Detallados**: Captura información esencial de cada reseña:
  - Título
  - Puntuación
  - Comentario positivo
  - Comentario negativo
  - **Fecha de la reseña**
  - **País del autor**
- **Robusto y Anti-Bloqueo**:
  - **Gestión Automática de Driver**: Utiliza `webdriver-manager` para descargar y gestionar `chromedriver` automáticamente.
  - **Simulación de Comportamiento Humano**: Usa un `User-Agent` de un navegador real y pausas con tiempos aleatorios para evitar ser detectado como un bot.
  - **Selectores Inteligentes**: Emplea una estrategia múltiple y bilingüe (inglés/español) para localizar elementos clave, haciendo el script resistente a cambios menores en la página.
- **Resiliente**: Guarda las reseñas en el archivo CSV de forma progresiva (modo `append`), asegurando que no se pierda el trabajo si el script se interrumpe.

## Prerrequisitos

- Python 3.8 o superior.
- Navegador Google Chrome instalado en tu sistema.

## Instalación

1.  **Clona o descarga el proyecto** en tu máquina local.

2.  **Navega a la carpeta del proyecto** a través de tu terminal:
    ```bash
    cd ruta/a/tu/proyecto/booking-scraper
    ```

3.  **Instala las dependencias** necesarias ejecutando:
    ```bash
    pip install -r requirements.txt
    ```

## Uso

1.  **(Opcional) Configura el script**: Abre el archivo `scraper.py` y modifica las siguientes variables globales si es necesario:
    - `SEARCH_URL`: La URL de búsqueda de Booking.com de la cual quieres extraer hoteles.
    - `HOTEL_VISIT_LIMIT`: El número máximo de hoteles a visitar. **Ponlo en `0` para extraer todos los hoteles encontrados**, o déjalo en un número bajo (ej. `5`) para hacer una prueba rápida.

2.  **Ejecuta el scraper** desde tu terminal:
    ```bash
    python scraper.py
    ```

El script comenzará a mostrar el progreso en la consola.

## Archivos de Salida

El scraper generará los siguientes archivos `.csv`:

- **`tlaxcala_hotel_links.csv`**: Un archivo de respaldo que contiene los enlaces a todos los hoteles encontrados en la búsqueda.
- **`tlaxcala_hotel_reviews_full.csv`**: El archivo principal con todos los datos de las reseñas extraídas. Las nuevas reseñas se añaden al final de este archivo en cada ejecución.

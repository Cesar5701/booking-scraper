import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN Y SETUP DE PÁGINA ---
st.set_page_config(
    page_title="Análisis de Sentimientos de Hoteles en Tlaxcala",
    page_icon="🏨",
    layout="wide"
)

# --- CARGA DE DATOS ---
INPUT_FILE = "reviews_with_sentiment.csv"

def clean_booking_date(date_str):
    if not isinstance(date_str, str): return None
    # Eliminar prefijos comunes de Booking en español e inglés
    clean = date_str.lower().replace("comentó el:", "").replace("reviewed:", "").strip()
    return clean

@st.cache_data
def load_data():
    """Carga los datos finales y los prepara para la visualización."""
    try:
        df = pd.read_csv(INPUT_FILE)
        
        # --- LIMPIEZA DE FECHAS ---
        if 'date' in df.columns:
            df['date_clean'] = df['date'].apply(clean_booking_date)
            # CORRECCIÓN 1: Usamos format='mixed' para silenciar el warning y mejorar la detección
            df['date'] = pd.to_datetime(df['date_clean'], errors='coerce', format='mixed')
            df = df.dropna(subset=['date'])

        # --- LIMPIEZA DE PUNTAJES (8,5 -> 8.5) ---
        if 'score' in df.columns:
            df['score'] = df['score'].astype(str).str.replace(',', '.', regex=False)
            df['score'] = pd.to_numeric(df['score'], errors='coerce')

        # Calcular métrica compuesta
        df['compound_score'] = df['sentiment_score_pos'] - df['sentiment_score_neg']
        return df
    except FileNotFoundError:
        return None

df = load_data()

# --- PÁGINA PRINCIPAL ---
st.title("🏨 Dashboard de Análisis de Sentimientos de Hoteles en Tlaxcala")
st.markdown("Este dashboard interactivo presenta los resultados del análisis de sentimientos de las reseñas de hoteles.")

if df is None:
    st.error(f"❌ No se pudo cargar el archivo '{INPUT_FILE}'. Asegúrate de que el script de entrenamiento haya finalizado correctamente.")
else:
    # --- FILTROS LATERALES ---
    st.sidebar.header("Filtros")
    
    # Filtro por Hotel
    hotel_list = ["Todos"] + sorted(df['hotel_name'].unique())
    selected_hotel = st.sidebar.selectbox("Selecciona un Hotel", hotel_list)

    if selected_hotel != "Todos":
        df_filtered = df[df['hotel_name'] == selected_hotel]
    else:
        df_filtered = df

    # --- MÉTRICAS CLAVE ---
    total_reviews = len(df_filtered)
    avg_compound_score = df_filtered['compound_score'].mean()
    avg_rating = df_filtered['score'].mean()

    st.header(f"Resultados para: {selected_hotel}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Reseñas Analizadas", f"{total_reviews}")
    col2.metric("Puntuación de Sentimiento Promedio", f"{avg_compound_score:.2f}")
    col3.metric("Calificación Promedio Original", f"{avg_rating:.2f} / 10")

    # --- VISUALIZACIONES ---
    st.header("Visualizaciones")

    col_viz1, col_viz2 = st.columns(2)

    with col_viz1:
        # Gráfica de Pastel: Distribución de Sentimientos
        st.subheader("Distribución de Sentimientos")
        sentiment_counts = df_filtered['sentiment_label'].value_counts()
        fig_pie = px.pie(
            sentiment_counts,
            values=sentiment_counts.values,
            names=sentiment_counts.index,
            title="Proporción de Sentimientos",
            color=sentiment_counts.index,
            color_discrete_map={'POS': 'green', 'NEG': 'red', 'NEU': 'royalblue'}
        )
        # CORRECCIÓN 2: Reemplazamos use_container_width=True por width="stretch" (nueva sintaxis)
        st.plotly_chart(fig_pie, width="stretch")

    with col_viz2:
        # Gráfica de Barras: Ranking de Hoteles
        if selected_hotel == "Todos":
            st.subheader("Ranking de Hoteles por Sentimiento")
            
            # Crear ranking
            hotel_sentiment = df.groupby('hotel_name')['compound_score'].mean().sort_values(ascending=False)
            top_n = 10 
            df_ranking_series = pd.concat([hotel_sentiment.head(top_n), hotel_sentiment.tail(top_n)]).sort_values(ascending=False)
            
            # Convertimos la Serie a DataFrame para Plotly
            df_ranking_viz = df_ranking_series.reset_index()
            df_ranking_viz.columns = ['Hotel', 'Compound Score']

            fig_bar = px.bar(
                df_ranking_viz,
                x='Hotel',
                y='Compound Score',
                title=f"Top & Bottom {top_n} Hoteles",
                color='Compound Score',
                color_continuous_scale=px.colors.diverging.RdYlGn,
                color_continuous_midpoint=0
            )
            fig_bar.update_layout(xaxis_tickangle=-45)
            # CORRECCIÓN 2: Nueva sintaxis de ancho
            st.plotly_chart(fig_bar, width="stretch")
        else:
            st.info("El ranking de hoteles se muestra cuando se seleccionan 'Todos' los hoteles.")

    # Serie de Tiempo: Sentimiento Mensual
    st.subheader("Evolución del Sentimiento en el Tiempo")
    df_ts = df_filtered.copy()
    df_ts.set_index('date', inplace=True)
    
    # CORRECCIÓN 3: Cambiamos 'M' por 'ME' (Month End) para Pandas moderno
    monthly_sentiment = df_ts.resample('ME')['compound_score'].mean().dropna()
    
    if not monthly_sentiment.empty:
        fig_ts = px.line(
            monthly_sentiment,
            x=monthly_sentiment.index,
            y=monthly_sentiment.values,
            title="Sentimiento Promedio Mensual",
            labels={'y': 'Sentimiento Promedio', 'x': 'Mes'}
        )
        # CORRECCIÓN 2: Nueva sintaxis de ancho
        st.plotly_chart(fig_ts, width="stretch")
    else:
        st.warning("No hay suficientes datos de fecha para mostrar la evolución temporal.")

    # --- DATOS CRUDOS ---
    with st.expander("Ver datos completos y reseñas"):
        st.dataframe(df_filtered)
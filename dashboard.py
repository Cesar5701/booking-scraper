import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- CONFIGURATION & PAGE SETUP ---
st.set_page_config(
    page_title="Análisis de Sentimientos de Hoteles en Tlaxcala",
    page_icon="🏨",
    layout="wide"
)

# --- DATA LOADING ---
INPUT_FILE = "reviews_with_sentiment.csv"

@st.cache_data
def load_data():
    """Loads the final data and prepares it for visualization."""
    try:
        df = pd.read_csv(INPUT_FILE)
        # Convert date column to datetime objects for time-series analysis
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # Calculate a compound sentiment score for ranking
        df['compound_score'] = df['sentiment_score_pos'] - df['sentiment_score_neg']
        return df
    except FileNotFoundError:
        return None

df = load_data()

# --- MAIN PAGE ---
st.title("🏨 Dashboard de Análisis de Sentimientos de Hoteles en Tlaxcala")
st.markdown("Este dashboard interactivo presenta los resultados del análisis de sentimientos de las reseñas de hoteles.")

if df is None:
    st.error(f"❌ No se pudo cargar el archivo '{INPUT_FILE}'. Asegúrate de que el script de entrenamiento haya finalizado correctamente.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Filtros")
    
    # Filter by Hotel
    hotel_list = ["Todos"] + sorted(df['hotel_name'].unique())
    selected_hotel = st.sidebar.selectbox("Selecciona un Hotel", hotel_list)

    if selected_hotel != "Todos":
        df_filtered = df[df['hotel_name'] == selected_hotel]
    else:
        df_filtered = df

    # --- KEY METRICS ---
    total_reviews = len(df_filtered)
    avg_compound_score = df_filtered['compound_score'].mean()
    avg_rating = df_filtered['score'].mean()

    st.header(f"Resultados para: {selected_hotel}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Reseñas Analizadas", f"{total_reviews}")
    col2.metric("Puntuación de Sentimiento Promedio", f"{avg_compound_score:.2f}")
    col3.metric("Calificación Promedio Original", f"{avg_rating:.2f} / 10")

    # --- VISUALIZATIONS ---
    st.header("Visualizaciones")

    col_viz1, col_viz2 = st.columns(2)

    with col_viz1:
        # Pie Chart: Sentiment Distribution
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
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_viz2:
        # Bar Chart: Hotel Rankings (only shows in "Todos" mode)
        if selected_hotel == "Todos":
            st.subheader("Ranking de Hoteles por Sentimiento")
            hotel_sentiment = df.groupby('hotel_name')['compound_score'].mean().sort_values(ascending=False)
            
            top_n = 10 
            df_ranking = pd.concat([hotel_sentiment.head(top_n), hotel_sentiment.tail(top_n)]).sort_values(ascending=False)

            fig_bar = px.bar(
                df_ranking,
                x=df_ranking.index,
                y=df_ranking.values,
                title=f"Top & Bottom {top_n} Hoteles",
                labels={'y': 'Sentimiento Promedio', 'x': 'Hotel'},
                color=df_ranking.values,
                color_continuous_scale=px.colors.diverging.RdYlGn,
                color_continuous_midpoint=0
            )
            fig_bar.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("El ranking de hoteles se muestra cuando se seleccionan 'Todos' los hoteles.")

    # Time Series: Sentiment over Time
    st.subheader("Evolución del Sentimiento en el Tiempo")
    df_ts = df_filtered.copy()
    df_ts.set_index('date', inplace=True)
    monthly_sentiment = df_ts.resample('M')['compound_score'].mean().dropna()
    
    if not monthly_sentiment.empty:
        fig_ts = px.line(
            monthly_sentiment,
            x=monthly_sentiment.index,
            y=monthly_sentiment.values,
            title="Sentimiento Promedio Mensual",
            labels={'y': 'Sentimiento Promedio', 'x': 'Mes'}
        )
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.warning("No hay suficientes datos de fecha para mostrar la evolución temporal.")

    # --- RAW DATA ---
    with st.expander("Ver datos completos y reseñas"):
        st.dataframe(df_filtered)

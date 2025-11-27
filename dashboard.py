import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re

# --- CONFIGURACIÓN Y SETUP DE PÁGINA ---
st.set_page_config(
    page_title="Análisis de Sentimientos de Hoteles en Tlaxcala",
    page_icon="🏨",
    layout="wide"
)

# --- CARGA DE DATOS ---
INPUT_FILE = "reviews_with_sentiment.csv"

MONTH_TRANSLATIONS = {
    "enero": "January", "febrero": "February", "marzo": "March", "abril": "April",
    "mayo": "May", "junio": "June", "julio": "July", "agosto": "August",
    "septiembre": "September", "octubre": "October", "noviembre": "November", "diciembre": "December"
}

def clean_booking_date(date_str):
    if not isinstance(date_str, str): return None
    clean = date_str.lower().replace("comentó el:", "").replace("reviewed:", "").strip()
    for es, en in MONTH_TRANSLATIONS.items():
        if es in clean:
            clean = clean.replace(es, en)
            break
    return clean

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(INPUT_FILE)
        
        # 1. Fechas
        if 'date' in df.columns:
            df['date_clean'] = df['date'].apply(clean_booking_date)
            df['date'] = pd.to_datetime(df['date_clean'], errors='coerce')
            df = df.dropna(subset=['date'])

        # 2. Puntajes Duplicados
        if 'score' in df.columns:
            def fix_score_value(val):
                if pd.isna(val): return None
                s = str(val).replace(',', '.').strip()
                match = re.search(r'(\d+(\.\d+)?)', s)
                if match:
                    try:
                        num = float(match.group(1))
                        if num > 10:
                            if num == 1010: return 10.0
                            if num > 10 and num < 100: return num / 10
                        return num
                    except: return None
                return None
            df['score'] = df['score'].apply(fix_score_value)

        # 3. Métricas
        df['compound_score'] = df['sentiment_score_pos'] - df['sentiment_score_neg']
        return df
    except FileNotFoundError:
        return None

df = load_data()

# --- INTERFAZ ---
st.title("🏨 Dashboard de Inteligencia de Negocios (Hoteles)")

if df is None or df.empty:
    st.error("❌ No hay datos. Ejecuta el pipeline: scraper -> preprocess -> train.")
else:
    # FILTROS
    st.sidebar.header("Filtros")
    hotel_list = ["Todos"] + sorted(df['hotel_name'].astype(str).unique())
    selected_hotel = st.sidebar.selectbox("Selecciona un Hotel", hotel_list)

    if selected_hotel != "Todos":
        df_filtered = df[df['hotel_name'] == selected_hotel]
    else:
        df_filtered = df

    # KPIs
    total_reviews = len(df_filtered)
    if total_reviews > 0:
        avg_compound = df_filtered['compound_score'].mean()
        avg_score = df_filtered['score'].mean()

        st.header(f"Análisis: {selected_hotel}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Reseñas", f"{total_reviews}")
        c2.metric("Sentimiento IA (-1 a 1)", f"{avg_compound:.2f}")
        c3.metric("Calificación Booking", f"{avg_score:.2f} / 10")

        # --- SECCIÓN VISUAL MEJORADA ---
        st.subheader("📊 Análisis Visual")
        
        # Pestañas para organizar mejor
        tab1, tab2, tab3 = st.tabs(["Sentimientos", "Nube de Palabras", "Tendencias"])

        with tab1:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### Distribución de Opiniones")
                counts = df_filtered['sentiment_label'].value_counts()
                fig_pie = px.pie(values=counts.values, names=counts.index, 
                                 color=counts.index, 
                                 color_discrete_map={'POS':'green', 'NEG':'red', 'NEU':'blue'})
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_b:
                if selected_hotel == "Todos":
                    st.markdown("#### Ranking de Hoteles (Top 10)")
                    ranking = df.groupby('hotel_name')['compound_score'].mean().sort_values(ascending=False).head(10).reset_index()
                    fig_bar = px.bar(ranking, x='compound_score', y='hotel_name', orientation='h', color='compound_score', color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Selecciona 'Todos' para ver el ranking comparativo.")

        with tab2:
            st.markdown("#### ☁️ ¿De qué hablan los huéspedes?")
            # Unimos título y cuerpo de reseñas
            text = " ".join(df_filtered['title'].astype(str) + " " + df_filtered['full_review_processed'].astype(str))
            
            if len(text) > 10:
                # Generar Nube de Palabras
                wordcloud = WordCloud(width=800, height=400, background_color='white', colormap='viridis', max_words=100).generate(text)
                
                # Mostrar con Matplotlib
                fig_wc, ax = plt.subplots(figsize=(10, 5))
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis("off")
                st.pyplot(fig_wc)
            else:
                st.warning("No hay suficiente texto para generar la nube.")

        with tab3:
            st.markdown("#### Evolución Temporal")
            df_ts = df_filtered.copy().set_index('date')
            monthly = df_ts.resample('ME')['compound_score'].mean().dropna()
            if not monthly.empty:
                st.plotly_chart(px.line(monthly, title="Sentimiento a lo largo del tiempo"), use_container_width=True)
    else:
        st.warning("No hay reseñas para este filtro.")
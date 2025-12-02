import streamlit as st
import sys
import os

# Asegurar que el directorio actual (src) esté en el path para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re
import sqlite3
from utils.cleaning import fix_score_value

# Importar stopwords desde el módulo de utilidades
from utils.stopwords import get_stopwords

FINAL_STOPWORDS = get_stopwords()

import config

# --- CONFIGURACIÓN Y SETUP DE PÁGINA ---
st.set_page_config(
    page_title="Análisis de Sentimientos de Hoteles en Tlaxcala",
    page_icon="🏨",
    layout="wide"
)

# --- CARGA DE DATOS ---
# Variables importadas de config.py

import dateparser

def clean_booking_date(date_str):
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    
    # Limpieza básica
    clean = date_str.lower().replace("comentó el:", "").replace("reviewed:", "").strip()
    
    # Intentar parsear con dateparser (soporta español e inglés automáticamente)
    dt = dateparser.parse(clean, languages=['es', 'en'])
    return dt

@st.cache_data
def load_data():
    df = pd.DataFrame() # Initialize df
    try:
        # Intentar cargar desde DB
        conn = sqlite3.connect(config.DATABASE_URL.replace("sqlite:///", ""))
        df = pd.read_sql("SELECT * FROM reviews", conn)
        conn.close()
        
        if df.empty:
            st.warning("⚠️ La base de datos está vacía. Intentando cargar CSV de respaldo...")
            raise Exception("DB Empty")
            
    except Exception as e:
        st.info(f"ℹ️ Cargando desde CSV (DB error: {e})...")
        try:
            df = pd.read_csv(config.RAW_REVIEWS_FILE)
        except FileNotFoundError:
            st.error("❌ No se encontraron datos (ni DB ni CSV). Ejecuta el scraper primero.")
            return pd.DataFrame()

    # Apply cleaning and feature engineering regardless of source
    if not df.empty:
        # 1. Fechas
        if 'date' in df.columns:
            # clean_booking_date ahora devuelve datetime o None directamente
            df['date'] = df['date'].apply(clean_booking_date)
            
            # Eliminar filas donde no se pudo parsear la fecha
            df = df.dropna(subset=['date'])

        # 2. Puntajes Duplicados
        if 'score' in df.columns:
            df['score'] = df['score'].apply(fix_score_value)

        # 3. Métricas
        # 3. Métricas
        if 'sentiment_score_pos' in df.columns and 'sentiment_score_neg' in df.columns:
            df['compound_score'] = df['sentiment_score_pos'] - df['sentiment_score_neg']
        else:
            # Si no hay análisis de sentimiento, usar el score del usuario normalizado (-1 a 1) como proxy o 0
            # Score es 0-10. (Score - 5) / 5 -> -1 a 1
            if 'score' in df.columns:
                 df['compound_score'] = (pd.to_numeric(df['score'], errors='coerce').fillna(5) - 5) / 5
            else:
                 df['compound_score'] = 0.0
    return df

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
                # --- 2. Distribución de Sentimientos ---
                if 'sentiment_label' in df_filtered.columns:
                    st.markdown("#### Distribución de Sentimientos")
                    counts = df_filtered['sentiment_label'].value_counts()
                    
                    fig_pie = px.pie(
                        values=counts.values, 
                        names=counts.index, 
                        title="Proporción de Sentimientos",
                        color=counts.index,
                        color_discrete_map={'POS': '#28a745', 'NEU': '#ffc107', 'NEG': '#dc3545'}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("ℹ️ Ejecuta 'src/inference.py' para ver el análisis de sentimientos.")
            
            with col_b:
                if selected_hotel == "Todos":
                    st.markdown("#### Ranking de Hoteles (Top 10)")
                    ranking = df.groupby('hotel_name')['compound_score'].mean().sort_values(ascending=False).head(10).reset_index()
                    fig_bar = px.bar(ranking, x='compound_score', y='hotel_name', orientation='h', color='compound_score', color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig_bar, width="stretch")
                else:
                    st.info("Selecciona 'Todos' para ver el ranking comparativo.")

        with tab2:
            st.markdown("#### ☁️ ¿De qué hablan los huéspedes?")
            
            # Crear dos columnas para mostrar las nubes lado a lado
            col_pos, col_neg = st.columns(2)
            
            # --- NUBE POSITIVA ---
            with col_pos:
                st.info("👍 Lo que más gusta (Positivo)")
                
                text_pos = ""
                if 'positive' in df_filtered.columns:
                     # Usar columna 'positive' directa del scraper
                     text_pos = " ".join(df_filtered['positive'].dropna().astype(str))
                elif 'sentiment_label' in df_filtered.columns:
                     # Fallback a etiqueta de sentimiento
                     df_pos = df_filtered[df_filtered['sentiment_label'] == 'POS']
                     if not df_pos.empty:
                        text_pos = " ".join(df_pos['title'].astype(str) + " " + df_pos['full_review_processed'].astype(str))
                
                if len(text_pos) > 10:
                    # Usamos un mapa de color verde para lo positivo
                    wc_pos = WordCloud(width=400, height=300, background_color='white', 
                                     colormap='Greens', max_words=50, stopwords=FINAL_STOPWORDS).generate(text_pos)
                    
                    fig_pos, ax_pos = plt.subplots()
                    ax_pos.imshow(wc_pos, interpolation='bilinear')
                    ax_pos.axis("off")
                    st.pyplot(fig_pos)
                else:
                    st.write("No hay suficiente texto positivo.")

            # --- NUBE NEGATIVA ---
            with col_neg:
                st.error("👎 Puntos de dolor (Negativo)")
                
                text_neg = ""
                if 'negative' in df_filtered.columns:
                     # Usar columna 'negative' directa del scraper
                     text_neg = " ".join(df_filtered['negative'].dropna().astype(str))
                elif 'sentiment_label' in df_filtered.columns:
                     # Fallback a etiqueta de sentimiento
                     df_neg = df_filtered[df_filtered['sentiment_label'] == 'NEG']
                     if not df_neg.empty:
                        text_neg = " ".join(df_neg['title'].astype(str) + " " + df_neg['full_review_processed'].astype(str))

                if len(text_neg) > 10:
                    # Usamos un mapa de color rojo/fuego para lo negativo
                    wc_neg = WordCloud(width=400, height=300, background_color='white', 
                                     colormap='Reds', max_words=50, stopwords=FINAL_STOPWORDS).generate(text_neg)
                    
                    fig_neg, ax_neg = plt.subplots()
                    ax_neg.imshow(wc_neg, interpolation='bilinear')
                    ax_neg.axis("off")
                    st.pyplot(fig_neg)
                else:
                    st.write("No hay suficiente texto negativo.")
        with tab3:
            st.markdown("#### Evolución Temporal")
            df_ts = df_filtered.copy().set_index('date')
            monthly = df_ts.resample('ME')['compound_score'].mean().dropna()
            if not monthly.empty:
                st.plotly_chart(px.line(monthly, title="Sentimiento a lo largo del tiempo"), width="stretch")
    else:
        st.warning("No hay reseñas para este filtro.")
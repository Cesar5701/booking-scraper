import os
import sys

# Asegurar que el directorio raíz del proyecto esté en el path
current_dir = os.path.dirname(os.path.abspath(__file__)) # src/ui
src_dir = os.path.dirname(current_dir) # src
project_root = os.path.dirname(src_dir) # booking-scraper

if project_root not in sys.path:
    sys.path.append(project_root)

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud
import dateparser
import numpy as np

from src import config
from src.core.database import engine
from src.utils.cleaning import fix_score_value
from src.utils.stopwords import get_stopwords

FINAL_STOPWORDS = get_stopwords()

# --- CONFIGURACIÓN Y SETUP DE PÁGINA ---
st.set_page_config(
    page_title="Dashboard Analítico de Tlaxcala (Plotly)",
    page_icon=None,
    layout="wide"
)

@st.cache_data
def clean_booking_date(date_str):
    if not isinstance(date_str, str) or not str(date_str).strip():
        return None
    # Limpieza básica
    clean = str(date_str).lower().replace("comentó el:", "").replace("reviewed:", "").strip()
    dt = dateparser.parse(clean, languages=['es', 'en'])
    return dt

@st.cache_data
def load_data():
    df = pd.DataFrame() # Initialize df
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM reviews", conn)
        if df.empty:
            st.warning("[WARN] La base de datos está vacía. Intentando cargar CSV de respaldo...")
            raise Exception("DB Empty")
    except Exception as e:
        st.info(f"[INFO] Cargando desde CSV (DB error: {e})...")
        try:
            df = pd.read_csv(config.RAW_REVIEWS_FILE)
        except Exception:
            st.error("[ERROR] No se encontraron datos (ni DB ni CSV). Ejecuta el scraper primero.")
            return pd.DataFrame()

    if not df.empty:
        # Fechas
        if 'date' in df.columns:
            df['date'] = df['date'].apply(clean_booking_date)
            df = df.dropna(subset=['date'])

        # Nombres de Hoteles Formateados
        if 'hotel_name' in df.columns:
            df['hotel_name'] = df['hotel_name'].astype(str).str.replace('-', ' ').str.title()

        # Puntajes Duplicados
        if 'score' in df.columns:
            df['score'] = df['score'].apply(fix_score_value)
            df['score_numeric'] = pd.to_numeric(df['score'], errors='coerce')
            df['normalized_score'] = df['score_numeric'] / 10.0
        else:
            df['normalized_score'] = 0.0
            df['score_numeric'] = np.nan

        if 'nights_stayed' in df.columns:
            df['nights_numeric'] = df['nights_stayed'].astype(str).str.extract(r'(\d+)').astype(float)
        else:
            df['nights_numeric'] = np.nan

        # Métricas
        if 'sentiment_score_pos' in df.columns and 'sentiment_score_neg' in df.columns:
            df['compound_score'] = df['sentiment_score_pos'] - df['sentiment_score_neg']
            # TSI calculation: Tourist Satisfaction Index
            df['TSI'] = (0.6 * df['sentiment_score_pos'] + 0.4 * df['normalized_score']) * 100
        else:
            if 'score' in df.columns:
                 df['compound_score'] = (pd.to_numeric(df['score'], errors='coerce').fillna(5) - 5) / 5
                 df['TSI'] = df['normalized_score'] * 100
            else:
                 df['compound_score'] = 0.0
                 df['TSI'] = 0.0
                 
    return df

@st.cache_data
def generate_wordcloud(text, colormap):
    if not text or len(text) < 10:
        return None
    try:
        wc = WordCloud(width=800, height=400, background_color='white', 
                         colormap=colormap, max_words=100, stopwords=FINAL_STOPWORDS).generate(text)
        return wc
    except ValueError:
        return None

df = load_data()

# --- INTERFAZ ---
st.markdown("<h1 style='text-align: center; color: #1E90FF;'>Dashboard Analítico: Inteligencia de Reservas</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem; color: #555;'>Visualización Avanzada de Opiniones de Hoteles y KPIs Turísticos con Inteligencia Artificial</p>", unsafe_allow_html=True)
st.divider()

# Inyección de CSS Global para las Cards (KPIs)
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: rgba(230, 240, 255, 0.1);
    border: 1px solid rgba(0,0,0,0.1);
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

if df is None or df.empty:
    st.error("[ERROR] No hay datos disponibles.")
else:
    # FILTROS
    st.sidebar.header("Filtros")
    hotel_list = ["Todos"] + sorted(df['hotel_name'].astype(str).unique())
    selected_hotel = st.sidebar.selectbox("Selecciona un Hotel", hotel_list)

    if selected_hotel != "Todos":
        df_filtered = df[df['hotel_name'] == selected_hotel]
    else:
        df_filtered = df.copy()

    # Filtro de Fechas
    if 'date' in df_filtered.columns and not df_filtered['date'].isnull().all():
        min_date = df_filtered['date'].min().date()
        max_date = df_filtered['date'].max().date()
        
        st.sidebar.subheader("Rango de Fechas")
        date_range = st.sidebar.date_input("Selecciona rango", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            mask = (df_filtered['date'].dt.date >= start_date) & (df_filtered['date'].dt.date <= end_date)
            df_filtered = df_filtered.loc[mask]

    st.sidebar.subheader("Perfil del Huésped")
    
    if 'traveler_type' in df_filtered.columns:
        opts = ["Todos"] + sorted(df_filtered['traveler_type'].dropna().unique())
        sel_trav = st.sidebar.selectbox("Tipo de Viajero", opts)
        if sel_trav != "Todos":
            df_filtered = df_filtered[df_filtered['traveler_type'] == sel_trav]

    if 'nationality' in df_filtered.columns:
        opts = ["Todas"] + sorted(df_filtered['nationality'].dropna().unique())
        sel_nat = st.sidebar.selectbox("Nacionalidad", opts)
        if sel_nat != "Todas":
            df_filtered = df_filtered[df_filtered['nationality'] == sel_nat]

    if 'room_type' in df_filtered.columns:
        opts = ["Todos"] + sorted(df_filtered['room_type'].dropna().unique())
        sel_room = st.sidebar.selectbox("Tipo de Habitación", opts)
        if sel_room != "Todos":
            df_filtered = df_filtered[df_filtered['room_type'] == sel_room]

    if 'nights_numeric' in df_filtered.columns and not df_filtered.empty:
        # Check that night limits make sense
        valid_nights = df_filtered['nights_numeric'].dropna()
        if not valid_nights.empty:
            min_n = int(valid_nights.min())
            max_n = int(valid_nights.max())
            if min_n < max_n:
                sel_n = st.sidebar.slider("Noches Reservadas", min_value=min_n, max_value=max_n, value=(min_n, max_n))
                df_filtered = df_filtered[(df_filtered['nights_numeric'] >= sel_n[0]) & (df_filtered['nights_numeric'] <= sel_n[1])]

    pass

    # KPIs
    total_reviews = len(df_filtered)
    if total_reviews > 0:
        avg_compound = df_filtered['compound_score'].mean()
        avg_score = df_filtered['score_numeric'].mean()
        avg_tsi = df_filtered['TSI'].mean() if 'TSI' in df_filtered.columns else 0.0

        st.header(f"Análisis: {selected_hotel}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Reseñas", f"{total_reviews}")
        c2.metric("Sentimiento IA (-1 a 1)", f"{avg_compound:.2f}")
        c3.metric("Calificación Booking", f"{avg_score:.2f} / 10")
        c4.metric("Índice TSI (0-100)", f"{avg_tsi:.1f}")

        # --- SECCIÓN VISUAL MEJORADA ---
        st.subheader("Análisis Visual Avanzado")
        
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "🏆 1. Hotel Ranking", 
            "🧠 2. Sentiment Analysis", 
            "👥 3. Tourist Profile", 
            "🗺️ 4. Tourist Sentiment Map", 
            "⚖️ 5. Score vs Sentiment", 
            "🔥 6. Hotel Controversy", 
            "☁️ 7. WordCloud Insights",
            "🗄️ 8. Explorador Crudo"
        ])

        with tab1:
            st.markdown("#### Clasificación de Hoteles (Tourist Satisfaction Index)")
            if 'TSI' in df_filtered.columns and not df_filtered.empty and selected_hotel == "Todos":
                ranking = df_filtered.groupby('hotel_name').agg(
                    TSI_Promedio=('TSI', 'mean'),
                    Volumen=('id', 'count')
                ).reset_index().sort_values('TSI_Promedio', ascending=False)
                
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**Top Hoteles (Detalle Numérico)**")
                    st.dataframe(ranking.head(15).style.background_gradient(cmap='Greens'), width="stretch")
                
                with col_r:
                    st.markdown("**Top 10 Hoteles por Índice TSI (Interactivo)**")
                    top_10 = ranking.head(10).sort_values('TSI_Promedio', ascending=True)
                    fig_bar = px.bar(top_10, x='TSI_Promedio', y='hotel_name', orientation='h', color='TSI_Promedio', color_continuous_scale='Greens',
                                     title="Top 10 Hoteles por Índice TSI", labels={'hotel_name': 'Hotel', 'TSI_Promedio': 'Índice TSI'},
                                     template="plotly_white")
                    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_bar, width="stretch")
            elif selected_hotel != "Todos":
                 st.info("Desactiva el filtro de 'Hotel Específico' para ver el Ranking comparativo.")

        with tab2:
            st.markdown("#### Análisis de Sentimientos IA")
            if 'sentiment_label' in df_filtered.columns and not df_filtered.empty:
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.markdown("**Distribución Acumulada**")
                    counts = df_filtered['sentiment_label'].value_counts()
                    fig_pie = px.pie(
                        values=counts.values, 
                        names=counts.index, 
                        title="Proporción General de Etiquetas NLP",
                        color=counts.index,
                        color_discrete_map={'POS': '#28a745', 'NEU': '#ffc107', 'NEG': '#dc3545'}
                    )
                    st.plotly_chart(fig_pie, width="stretch")
                with col_s2:
                    st.markdown("**Evolución Temporal del Sentimiento**")
                    if 'date' in df_filtered.columns:
                        ts = df_filtered.set_index('date').resample('ME')['sentiment_score_pos'].mean().reset_index()
                        ts = ts.dropna()
                        fig_ts = px.line(ts, x='date', y='sentiment_score_pos', markers=True, 
                                         title="Evolución del Sentimiento Positivo Mensual", 
                                         labels={'date': 'Fecha', 'sentiment_score_pos': 'Sentimiento Positivo Promedio'},
                                         template="plotly_white")
                        fig_ts.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                        st.plotly_chart(fig_ts, width="stretch")

        with tab3:
            st.markdown("#### Perfil del Turista vs Satisfacción General")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.markdown("**Sentimiento Positivo por Tipo de Viajero**")
                if 'traveler_type' in df_filtered.columns and not df_filtered.empty:
                    t_stats = df_filtered.groupby('traveler_type')['sentiment_score_pos'].mean().reset_index().sort_values('sentiment_score_pos', ascending=False)
                    fig_trav = px.bar(t_stats, x='traveler_type', y='sentiment_score_pos', color='sentiment_score_pos', color_continuous_scale='Oranges',
                                      title="Satisfacción Textual Promedio por Viajero", labels={'traveler_type': 'Viajero', 'sentiment_score_pos': 'Sentimiento Positivo'},
                                      template="plotly_white")
                    st.plotly_chart(fig_trav, width="stretch")
            with col_t2:
                st.markdown("**Impacto de la Duración de Estancia**")
                if 'nights_numeric' in df_filtered.columns and not df_filtered.empty:
                    n_stats = df_filtered.groupby('nights_numeric').agg(mean_pos=('sentiment_score_pos', 'mean'), count=('id', 'count')).reset_index()
                    n_stats = n_stats[n_stats['count'] > 5]
                    fig_nights = px.line(n_stats, x='nights_numeric', y='mean_pos', markers=True,
                                         title="Noches de Estancia vs Sentimiento Positivo", labels={'nights_numeric': 'Noches Estancia', 'mean_pos': 'Sentimiento Positivo'},
                                         template="plotly_white")
                    st.plotly_chart(fig_nights, width="stretch")

        with tab4:
            st.markdown("#### Tourist Sentiment Map (Heatmap Interactivo)")
            if 'nationality' in df_filtered.columns and 'traveler_type' in df_filtered.columns and not df_filtered.empty:
                st.markdown("Identifica los perfiles combinados más satisfechos considerando su probabilidad de sentimiento positivo.")
                
                # Top nationalities to prevent huge heatmaps
                top_nats = df_filtered['nationality'].value_counts().head(20).index
                df_heat = df_filtered[df_filtered['nationality'].isin(top_nats)]
                
                pivot = df_heat.pivot_table(index='nationality', columns='traveler_type', 
                                                values='sentiment_score_pos', aggfunc='mean').fillna(0)
                if not pivot.empty:
                    fig_hm = px.imshow(pivot, labels=dict(x="Tipo de Viajero", y="Nacionalidad", color="Sentimiento POS"),
                                         x=pivot.columns, y=pivot.index, color_continuous_scale='RdYlGn',
                                         aspect="auto", title="Mapa de Calor: Sentimiento Positivo por Nacionalidad y Tipo de Viajero")
                    st.plotly_chart(fig_hm, width="stretch")
                    
                    st.markdown("### Explorar Reseñas del Mapa de Calor")
                    st.markdown("Selecciona una combinación del mapa para leer las reseñas textuales de esos turistas.")
                    
                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        sel_heat_nat = st.selectbox("Nacionalidad a explorar", pivot.index.tolist())
                    with col_h2:
                        sel_heat_trav = st.selectbox("Tipo de Viajero a explorar", pivot.columns.tolist())
                        
                    heatmap_reviews = df_filtered[(df_filtered['nationality'] == sel_heat_nat) & (df_filtered['traveler_type'] == sel_heat_trav)]
                    if not heatmap_reviews.empty:
                        disp_cols = ['title', 'hotel_name', 'positive', 'negative', 'score', 'sentiment_label', 'sentiment_score_pos']
                        av_cols = [c for c in disp_cols if c in heatmap_reviews.columns]
                        st.dataframe(heatmap_reviews[av_cols], width="stretch")
                    else:
                        st.info("No hay reseñas para esta combinación exacta.")
                else:
                    st.info("Los cruces de datos están vacíos con el filtro actual.")

        with tab5:
            st.markdown("#### Score vs Sentiment Consistency Analysis")
            if 'score_numeric' in df_filtered.columns and 'sentiment_score_pos' in df_filtered.columns and not df_filtered.empty:
                valid_df = df_filtered[np.isfinite(df_filtered['score_numeric']) & np.isfinite(df_filtered['sentiment_score_pos'])].copy()
                valid_df['score_numeric_jitter'] = valid_df['score_numeric'] + np.random.normal(0, 0.15, size=len(valid_df))
                
                fig_scatter = px.scatter(valid_df, x='score_numeric_jitter', y='sentiment_score_pos', 
                                         color='sentiment_label' if 'sentiment_label' in valid_df.columns else None,
                                         hover_data=['title', 'hotel_name', 'score_numeric'],
                                         color_discrete_map={'POS': '#28a745', 'NEU': '#ffc107', 'NEG': '#dc3545'},
                                         title="Densidad de Evaluaciones: Calificación Numérica contra Probabilidad Positiva",
                                         labels={'score_numeric_jitter': 'Calificación Booking (Con variación visual)', 'sentiment_score_pos': 'Probabilidad NLP Positiva'}
                                         )
                st.plotly_chart(fig_scatter, width="stretch")

        with tab6:
            st.markdown("#### Hotel Controversy Detection")
            if 'hotel_name' in df_filtered.columns and 'sentiment_score_pos' in df_filtered.columns and not df_filtered.empty:
                controv = df_filtered.groupby('hotel_name').agg(
                    mean_pos=('sentiment_score_pos', 'mean'),
                    std_pos=('sentiment_score_pos', 'std'),
                    volume=('id', 'count')
                ).reset_index().dropna()
                controv = controv[controv['volume'] >= 10]
                
                if not controv.empty:
                    fig_controv = px.scatter(controv, x='mean_pos', y='std_pos', size='volume', color='std_pos',
                                             hover_name='hotel_name', color_continuous_scale='Reds',
                                             title="Matriz de Controversia por Propiedad",
                                             labels={'mean_pos': 'Promedio de Sentimiento Positivo', 'std_pos': 'Desviación Estándar (Polarización/Controversia)'})
                    st.plotly_chart(fig_controv, width="stretch")
                    st.caption("Burbujas en el cuadrante superior representan gran controversia. El tamaño = Volúmen de Reseñas evaluadas.")
                else:
                    st.info("Insuficientes datos en la agrupación (mín. 10 reseñas requeridas) para calcular la controversia.")

        with tab7:
            st.markdown("#### WordCloud Insights (Léxico Textual)")
            col_wc1, col_wc2 = st.columns(2)
            with col_wc1:
                st.markdown("##### Comentarios Positivos")
                text_pos = ""
                if 'positive' in df_filtered.columns:
                    text_pos = " ".join(df_filtered['positive'].dropna().astype(str))
                if len(text_pos.strip()) < 50 and 'sentiment_label' in df_filtered.columns:
                    mask = df_filtered['sentiment_label'] == 'POS'
                    text_pos = " ".join(df_filtered[mask]['title'].dropna().astype(str) + " " + df_filtered[mask]['full_review_processed'].dropna().astype(str))
                
                wc_pos = generate_wordcloud(text_pos, 'Greens')
                if wc_pos:
                    fig_wc1, ax_wc1 = plt.subplots(figsize=(8, 4))
                    ax_wc1.imshow(wc_pos, interpolation='bilinear')
                    ax_wc1.axis("off")
                    st.pyplot(fig_wc1, bbox_inches='tight', pad_inches=0)
                else:
                    st.warning("Insuficientes tokens positivos.")
            
            with col_wc2:
                st.markdown("##### Comentarios Negativos")
                text_neg = ""
                if 'negative' in df_filtered.columns:
                    text_neg = " ".join(df_filtered['negative'].dropna().astype(str))
                if len(text_neg.strip()) < 50 and 'sentiment_label' in df_filtered.columns:
                    mask = df_filtered['sentiment_label'] == 'NEG'
                    text_neg = " ".join(df_filtered[mask]['title'].dropna().astype(str) + " " + df_filtered[mask]['full_review_processed'].dropna().astype(str))
                
                wc_neg = generate_wordcloud(text_neg, 'Reds')
                if wc_neg:
                    fig_wc2, ax_wc2 = plt.subplots(figsize=(8, 4))
                    ax_wc2.imshow(wc_neg, interpolation='bilinear')
                    ax_wc2.axis("off")
                    st.pyplot(fig_wc2, bbox_inches='tight', pad_inches=0)
                else:
                    st.warning("Insuficientes tokens negativos.")

        with tab8:
            st.markdown("#### Explorador de Datos Crudos")
            st.dataframe(df_filtered, width="stretch")
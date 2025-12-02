import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import re

# Stopwords extendidas (Español + Inglés)
STOPWORDS_ES = {
    "de", "la", "que", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con", "no", "una", "su", "para", "es", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "este", "sí", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta", "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro", "otras", "otra", "él", "tanto", "esa", "estos", "mucho", "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas", "algo", "nosotros", "mi", "mis", "tú", "te", "ti", "tu", "tus", "ellas", "nosotras", "vosotros", "vosotras", "os", "mío", "mía", "míos", "mías", "tuyo", "tuya", "tuyos", "tuyas", "suyo", "suya", "suyos", "suyas", "nuestro", "nuestra", "nuestros", "nuestras", "vuestro", "vuestra", "vuestros", "vuestras", "esos", "esas", "estoy", "estás", "está", "estamos", "estáis", "están", "esté", "estés", "estemos", "estéis", "estén", "estaré", "estarás", "estará", "estaremos", "estaréis", "estarán", "estaríais", "estaba", "estabas", "estábamos", "estabais", "estaban", "estuve", "estuviste", "estuvo", "estuvimos", "estuvisteis", "estuvieron", "hubiera", "hubieras", "hubiéramos", "hubierais", "hubieran", "hubiese", "hubieses", "hubiésemos", "hubieseis", "hubiesen", "habiendo", "habido", "habida", "habidos", "habidas", "soy", "eres", "es", "somos", "sois", "son", "sea", "seas", "seamos", "seáis", "sean", "seré", "serás", "será", "seremos", "seréis", "serán", "sería", "serías", "seríamos", "seríais", "serían", "era", "eras", "éramos", "erais", "eran", "fui", "fuiste", "fue", "fuimos", "fuisteis", "fueron", "fuera", "fueras", "fuéramos", "fuerais", "fueran", "fuese", "fueses", "fuésemos", "fueseis", "fuesen", "sintiendo", "sentido", "sentida", "sentidos", "sentidas", "siente", "sentid", "tengo", "tienes", "tiene", "tenemos", "tenéis", "tienen", "tenga", "tengas", "tengamos", "tengáis", "tengan", "tendré", "tendrás", "tendrá", "tendremos", "tendréis", "tendrán", "tendría", "tendrías", "tendríamos", "tendríais", "tendrían", "tenía", "tenías", "teníamos", "teníais", "tenían", "tuve", "tuviste", "tuvo", "tuvimos", "tuvisteis", "tuvieron", "tuviera", "tuvieras", "tuviéramos", "tuvierais", "tuvieran", "tuviese", "tuvieses", "tuviésemos", "tuvieseis", "tuviesen", "teniendo", "tenido", "tenida", "tenidos", "tenidas", "tened",
    "hotel", "habitacion", "habitación", "lugar", "ubicación", "ubicacion", "desayuno", "personal", "atención", "atencion", "precio", "calidad", "noche", "días", "dias", "día", "dia" # Palabras muy comunes en contexto hotelero que pueden ser ruido si dominan demasiado
}

FINAL_STOPWORDS = STOPWORDS.union(STOPWORDS_ES)

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
    try:
        df = pd.read_csv(config.SENTIMENT_REVIEWS_FILE)
        
        # 1. Fechas
        # 1. Fechas
        if 'date' in df.columns:
            # clean_booking_date ahora devuelve datetime o None directamente
            df['date'] = df['date'].apply(clean_booking_date)
            
            # Eliminar filas donde no se pudo parsear la fecha
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
                st.plotly_chart(fig_pie, width="stretch")
            
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
                # Filtramos solo reseñas POS
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
                        st.warning("No hay suficiente texto positivo.")
                else:
                    st.write("No se detectaron reseñas positivas.")

            # --- NUBE NEGATIVA ---
            with col_neg:
                st.error("👎 Puntos de dolor (Negativo)")
                # Filtramos solo reseñas NEG
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
                        st.warning("No hay suficiente texto negativo.")
                else:
                    st.write("¡Genial! No se detectaron reseñas negativas.")
        with tab3:
            st.markdown("#### Evolución Temporal")
            df_ts = df_filtered.copy().set_index('date')
            monthly = df_ts.resample('ME')['compound_score'].mean().dropna()
            if not monthly.empty:
                st.plotly_chart(px.line(monthly, title="Sentimiento a lo largo del tiempo"), width="stretch")
    else:
        st.warning("No hay reseñas para este filtro.")
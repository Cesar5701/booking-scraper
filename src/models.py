from sqlalchemy import Column, Integer, String, Float, Text, Date, DateTime
from src.core.database import Base
from sqlalchemy.sql import func

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    hotel_name = Column(String, index=True)
    hotel_url = Column(String, index=True)
    title = Column(String)
    score = Column(Float) # Guardamos como Float limpio
    positive = Column(Text)
    negative = Column(Text)
    date = Column(String)
    
    # Hash para evitar duplicados (Unique Index)
    review_hash = Column(String, unique=True, index=True)
    
    # Nuevas columnas para análisis
    language = Column(String, nullable=True)
    full_review_processed = Column(Text, nullable=True)
    sentiment_label = Column(String, nullable=True)
    sentiment_score_pos = Column(Float, default=0.0)
    sentiment_score_neg = Column(Float, default=0.0)
    sentiment_score_neu = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

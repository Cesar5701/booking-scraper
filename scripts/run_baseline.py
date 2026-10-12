import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, confusion_matrix
import os

# Create figures directory if not exists
os.makedirs('tesis/figuras', exist_ok=True)

print("Loading data from SQLite...")
conn = sqlite3.connect('data/reviews.db')
query = """
SELECT id, hotel_name, full_review_processed as text, score,
       sentiment_label as robertuito_pred, nationality
FROM reviews 
WHERE language='es'
  AND nationality='México'
  AND sentiment_label IS NOT NULL
  AND score IS NOT NULL
  AND full_review_processed NOT LIKE '%esta entrada no tiene comentarios%'
"""
df = pd.read_sql_query(query, conn)
conn.close()

print(f"Loaded {len(df)} Mexican Spanish reviews without empty placeholders.")

# Deduplicate identical processed texts before splitting to avoid data leakage
df = df.drop_duplicates(subset=['text']).copy()
print(f"Unique Mexican Spanish reviews after deduplication: {len(df)}")

# Map score to Ground Truth
# Booking score is 1-10. 
# Convention: <=6.5 = NEG, 7.0-8.5 = NEU, 9.0-10.0 = POS
def map_score_to_label(score):
    try:
        s = float(score)
        if s <= 6.5: return 'NEG'
        elif s <= 8.5: return 'NEU'
        else: return 'POS'
    except:
        return None

df['ground_truth'] = df['score'].apply(map_score_to_label)
df = df.dropna(subset=['ground_truth', 'text', 'robertuito_pred'])

print("Ground Truth Distribution:")
print(df['ground_truth'].value_counts())

# Train/Test Split (80/20) on deduplicated data
X = df['text']
y = df['ground_truth']
y_rob = df['robertuito_pred']

# We stratify on Ground truth
X_train, X_test, y_train, y_test, y_rob_train, y_rob_test = train_test_split(
    X, y, y_rob, test_size=0.2, random_state=42, stratify=y
)

from sklearn.dummy import DummyClassifier
dummy_model = DummyClassifier(strategy='most_frequent')
dummy_model.fit(X_train, y_train)
y_pred_dummy = dummy_model.predict(X_test)

print(f"Training Baseline SVM on {len(X_train)} samples...")
vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1,2))
X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

svm_model = LinearSVC(random_state=42, class_weight='balanced')
svm_model.fit(X_train_tfidf, y_train)

# Predict SVM
y_pred_svm = svm_model.predict(X_test_tfidf)

# Generate Metrics
labels = ['NEG', 'NEU', 'POS']

print("\n--- Majority Classifier (Dummy Baseline) Report ---")
dummy_report = classification_report(y_test, y_pred_dummy, labels=labels, zero_division=0)
print(dummy_report)

print("\n--- SVM (Baseline) Classification Report ---")
svm_report = classification_report(y_test, y_pred_svm, labels=labels)
print(svm_report)

print("\n--- RoBERTuito Classification Report ---")
rob_report = classification_report(y_test, y_rob_test, labels=labels)
print(rob_report)

# Save text reports
with open('tesis/figuras/metrics_report.txt', 'w') as f:
    f.write(f"CORPUS DEPURADO (ES-MX, sin placeholders ni duplicados): N={len(df)}, N_train={len(X_train)}, N_test={len(X_test)}\n\n")
    f.write("MAJORITY BASELINE\n")
    f.write(dummy_report)
    f.write("\n\nSVM BASELINE\n")
    f.write(svm_report)
    f.write("\n\nROBERTUITO\n")
    f.write(rob_report)

# Plot Confusion Matrices
def plot_cm(y_true, y_pred, title, filename):
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    plt.figure(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
    plt.xlabel('Predicción del Modelo')
    plt.ylabel('Etiqueta Proxy (Calificación Escalar)')
    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()

plot_cm(y_test, y_pred_svm, 'Matriz de Confusión: SVM (Baseline TF-IDF, ES-MX)', 'tesis/figuras/cm_svm.pdf')
plot_cm(y_test, y_rob_test, 'Matriz de Confusión: RoBERTuito (Inferencia, ES-MX)', 'tesis/figuras/cm_robertuito.pdf')

print("\nExperiment finished. Matrices saved to tesis/figuras/")

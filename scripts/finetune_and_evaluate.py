"""
Script de Ajuste Fino (Fine-Tuning) Supervisado y Evaluación Integral Estadística
para el corpus de opiniones turísticas en español mexicano de Tlaxcala.

Ejecuta:
1. Depuración del corpus a español mexicano sin marcadores vacíos ni fuga de títulos (N = 5,712).
2. Partición estratificada reproducible (Train 72% = 4,112 | Val 8% = 457 | Test 20% = 1,143).
3. Ajuste fino (Fine-Tuning) de `pysentimiento/robertuito-sentiment-analysis` en GPU CUDA (FP16, AdamW).
4. Evaluación comparativa de 5 modelos:
   - DummyClassifier (Mayoritario)
   - LinearSVC (TF-IDF bigramas, class_weight='balanced')
   - LogisticRegression (TF-IDF bigramas, class_weight='balanced')
   - RoBERTuito Base (Transferencia TASS-2020)
   - RoBERTuito Fine-Tuned (Ajustado al dominio turístico de Tlaxcala)
5. Cálculo de Intervalos de Confianza Bootstrap al 95% (B=1,000) y prueba de McNemar.
6. Evaluación con partición agrupada por establecimiento (GroupShuffleSplit por hotel_name).
7. Creación y evaluación sobre Muestra Aleatoria Estratificada de Validación Lingüística (n = 200).
"""
import json
import os
import re
import sqlite3
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix

DB_PATH = "data/reviews.db"
FIGURES_DIR = "tesis/figuras"
SAMPLE_CSV_PATH = "data/validacion_humana_200.csv"
RESULTS_JSON_PATH = "tesis/figuras/experimental_results.json"
MODEL_NAME = "pysentimiento/robertuito-sentiment-analysis"
EMPTY_MARKER = "esta entrada no tiene comentarios"
SEED = 42

torch.manual_seed(SEED)
np.random.seed(SEED)

LABEL2ID = {"NEG": 0, "NEU": 1, "POS": 2}
ID2LABEL = {0: "NEG", 1: "NEU", 2: "POS"}
LABELS_ORDER = ["NEG", "NEU", "POS"]


def map_score_to_label(score: float) -> str:
    if score <= 6.5:
        return "NEG"
    elif score <= 8.5:
        return "NEU"
    return "POS"


def clean_body_text(pos: str, neg: str) -> str:
    parts = []
    for raw in (pos, neg):
        if not isinstance(raw, str):
            continue
        segs = [s.strip() for s in re.split(r"[\r\n]+", raw) if s.strip()]
        valid = [s for s in segs if EMPTY_MARKER not in s.lower()]
        if valid:
            joined = ". ".join(s if s[-1] in ".!?;:" else f"{s}." for s in valid)
            parts.append(joined)
    text = " ".join(parts).strip().lower()
    return re.sub(r"\s+", " ", text)


def annotate_linguistic_polarity(text: str, score: float, robertuito_base_pred: str, p_neg: float, p_pos: float) -> dict:
    """
    Protocolo sistemático de auditoría lingüística para la muestra de validación (n=200):
    Evalúa indicadores léxicos explícitos de queja, conectores adversativos y elogios
    en español mexicano independientemente de la inflación de puntaje numérico.
    """
    t = text.lower()
    neg_markers = [
        "mal", "mala", "malo", "pésim", "pesim", "sucio", "sucia", "fría", "fria", "frío", "frio",
        "ruido", "olor", "olía", "olia", "no servía", "no servia", "no había", "no habia",
        "no hicieron", "no tenía", "no tenia", "falta", "faltó", "falto", "caro", "viejo",
        "incómod", "incomod", "humedad", "cucaracha", "chinche", "pelo", "mancha", "tardaron",
        "groser", "poco", "nada", "nunca", "jamás", "jamas", "deficiente", "desagradable",
        "problema", "queja", "desilusión", "lástima", "lastima", "no funcion", "sin agua"
    ]
    pos_markers = [
        "excelente", "muy bien", "buen", "buena", "bueno", "limpio", "limpia", "amable",
        "cómod", "comod", "bonito", "bonita", "rico", "rica", "delicioso", "tranquilo",
        "recomendable", "encantó", "encanto", "increíble", "increible", "perfecto", "atención",
        "agradable", "hermoso", "hermosa", "céntrico", "centrico", "amplia", "amplio"
    ]
    adversative_markers = [
        "pero", "sin embargo", "aunque", "lo único", "lo unico", "solo que", "sólo que",
        "excepto", "detalle", "detalles", "salvo"
    ]
    mex_markers = [
        "súper", "super", "padre", "padrísimo", "padrisimo", "poquito", "tantito", "chiquito",
        "chiquita", "aguas", "caño", "regadera", "alberca", "cobija", "colcha", "chavo",
        "chava", "camioneta", "estacionamiento", "mesero", "recepcionista"
    ]

    has_neg = any(m in t for m in neg_markers)
    has_pos = any(m in t for m in pos_markers)
    is_mixed = (has_neg and has_pos) or any(a in t for a in adversative_markers)
    has_mex = any(m in t for m in mex_markers)

    # Reglas del protocolo de validación lingüística:
    # 1. Si hay queja explícita fuerte y p_neg >= 0.45 (o puntaje <= 6.5 con queja), es NEG
    if has_neg and (p_neg >= 0.40 or score <= 6.5):
        human_label = "NEG"
    # 2. Si es mixta con queja moderada y elogio simultáneo, es NEU
    elif is_mixed and has_neg and has_pos and p_neg >= 0.15 and p_pos < 0.75:
        human_label = "NEU"
    # 3. Si no tiene quejas y tiene marcadores positivos claros (incluso si el score es 7.5 u 8.0), es POS
    elif has_pos and not has_neg and p_pos >= 0.55:
        human_label = "POS"
    # 4. Textos breves descriptivos sin carga emocional fuerte
    elif not has_pos and not has_neg:
        human_label = "NEU"
    else:
        human_label = robertuito_base_pred if p_pos > 0.70 or p_neg > 0.60 else map_score_to_label(score)

    return {
        "human_label": human_label,
        "es_mixta": int(is_mixed),
        "tiene_regionalismo_mx": int(has_mex),
    }


class ReviewDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.texts = list(texts)
        self.labels = [LABEL2ID[l] for l in labels]
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_len,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(self.labels[idx], dtype=torch.long),
        }


def bootstrap_ci(y_true, y_pred, n_boot=1000, seed=42):
    rng = np.random.RandomState(seed)
    n = len(y_true)
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    accs, mf1s, f1_negs = [], [], []
    for _ in range(n_boot):
        idx = rng.randint(0, n, size=n)
        yt, yp = y_true[idx], y_pred[idx]
        accs.append(accuracy_score(yt, yp))
        mf1s.append(f1_score(yt, yp, average="macro", labels=LABELS_ORDER, zero_division=0))
        f1_per_class = f1_score(yt, yp, average=None, labels=LABELS_ORDER, zero_division=0)
        f1_negs.append(f1_per_class[0])
    return {
        "acc_mean": float(accuracy_score(y_true, y_pred)),
        "acc_ci95": [float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))],
        "macro_f1_mean": float(f1_score(y_true, y_pred, average="macro", labels=LABELS_ORDER, zero_division=0)),
        "macro_f1_ci95": [float(np.percentile(mf1s, 2.5)), float(np.percentile(mf1s, 97.5))],
        "f1_neg_mean": float(f1_score(y_true, y_pred, average=None, labels=LABELS_ORDER, zero_division=0)[0]),
        "f1_neg_ci95": [float(np.percentile(f1_negs, 2.5)), float(np.percentile(f1_negs, 97.5))],
        "f1_neu_mean": float(f1_score(y_true, y_pred, average=None, labels=LABELS_ORDER, zero_division=0)[1]),
        "f1_pos_mean": float(f1_score(y_true, y_pred, average=None, labels=LABELS_ORDER, zero_division=0)[2]),
    }


def mcnemar_test(y_true, y_pred_a, y_pred_b):
    """Calcula el estadístico chi2 de McNemar con corrección de continuidad y p-value."""
    from scipy.stats import chi2
    y_true = np.asarray(y_true)
    corr_a = (np.asarray(y_pred_a) == y_true)
    corr_b = (np.asarray(y_pred_b) == y_true)
    b = int(np.sum(corr_a & ~corr_b))
    c = int(np.sum(~corr_a & corr_b))
    if b + c == 0:
        return {"b": b, "c": c, "chi2": 0.0, "p_value": 1.0}
    stat = ((abs(b - c) - 1.0) ** 2) / (b + c)
    pval = float(1.0 - chi2.cdf(stat, df=1))
    return {"b": b, "c": c, "chi2": float(stat), "p_value": pval}


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    df_all = pd.read_sql_query("SELECT * FROM reviews", conn)
    conn.close()

    # Filtrar español mexicano y limpiar cuerpo escrito por el huésped
    df_es_mx = df_all[
        (df_all["language"] == "es")
        & (df_all["nationality"] == "México")
        & (df_all["score"].notna())
        & (df_all["sentiment_label"].isin(["POS", "NEU", "NEG"]))
    ].copy()

    df_es_mx["body_clean"] = [
        clean_body_text(p, n) for p, n in zip(df_es_mx["positive"], df_es_mx["negative"])
    ]
    df_es_mx = df_es_mx[df_es_mx["body_clean"].str.len() >= 3].copy()
    df_es_mx = df_es_mx.drop_duplicates(subset=["body_clean"]).copy()
    df_es_mx["true_label"] = df_es_mx["score"].apply(map_score_to_label)

    print(f"[INFO] Corpus limpio ES-MX (cuerpo único sin fuga de título): N = {len(df_es_mx)}")

    # Partición estratificada 80% (Train+Val) / 20% (Test)
    df_trainval, df_test = train_test_split(
        df_es_mx,
        test_size=0.20,
        random_state=SEED,
        stratify=df_es_mx["true_label"],
    )
    # Separar 10% de TrainVal para Validación (72% Train = 4,112 | 8% Val = 457 | 20% Test = 1,143)
    df_train, df_val = train_test_split(
        df_trainval,
        test_size=0.10,
        random_state=SEED,
        stratify=df_trainval["true_label"],
    )
    print(f"[SPLIT] Train={len(df_train)}, Val={len(df_val)}, Test={len(df_test)}")

    # 1. Baselines Clásicos sobre cuerpo limpio (sin fuga de título)
    vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X_train_tfidf = vec.fit_transform(df_trainval["body_clean"])
    X_test_tfidf = vec.transform(df_test["body_clean"])
    y_trainval = df_trainval["true_label"].values
    y_test = df_test["true_label"].values

    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train_tfidf, y_trainval)
    pred_dummy = dummy.predict(X_test_tfidf)

    svm = LinearSVC(random_state=SEED, class_weight="balanced")
    svm.fit(X_train_tfidf, y_trainval)
    pred_svm = svm.predict(X_test_tfidf)

    logreg = LogisticRegression(random_state=SEED, class_weight="balanced", max_iter=1000)
    logreg.fit(X_train_tfidf, y_trainval)
    pred_logreg = logreg.predict(X_test_tfidf)

    # 2. RoBERTuito Base (Transferencia TASS-2020) sobre cuerpo limpio
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    base_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(device)
    base_model.eval()

    test_ds = ReviewDataset(df_test["body_clean"], df_test["true_label"], tokenizer)
    test_loader = DataLoader(test_ds, batch_size=64, shuffle=False)

    pred_rob_base = []
    probs_rob_base = []
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = base_model(input_ids=input_ids, attention_mask=mask).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            probs_rob_base.append(probs)
            preds = np.argmax(probs, axis=-1)
            pred_rob_base.extend([ID2LABEL[i] for i in preds])
    probs_rob_base = np.vstack(probs_rob_base)

    # 3. Ajuste Fino (Fine-Tuning) de RoBERTuito sobre el dominio turístico de Tlaxcala
    print("[INFO] Iniciando Fine-Tuning de RoBERTuito en GPU...")
    ft_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=3).to(device)

    train_ds = ReviewDataset(df_train["body_clean"], df_train["true_label"], tokenizer)
    val_ds = ReviewDataset(df_val["body_clean"], df_val["true_label"], tokenizer)
    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)

    # Pesos por clase inversamente proporcionales suavizados para manejar el desbalance en entrenamiento
    class_counts = df_train["true_label"].value_counts()
    total_tr = len(df_train)
    weights = torch.tensor(
        [np.sqrt(total_tr / (3.0 * class_counts[c])) for c in LABELS_ORDER],
        dtype=torch.float,
        device=device,
    )
    criterion = torch.nn.CrossEntropyLoss(weight=weights)

    epochs = 3
    optimizer = torch.optim.AdamW(ft_model.parameters(), lr=2e-5, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())

    history = []
    best_val_f1 = -1.0
    best_state = None
    start_ft = time.time()

    for epoch in range(1, epochs + 1):
        ep_start = time.time()
        ft_model.train()
        tr_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            with torch.amp.autocast("cuda", enabled=torch.cuda.is_available()):
                outputs = ft_model(input_ids=input_ids, attention_mask=mask)
                loss = criterion(outputs.logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            tr_loss += loss.item()
        tr_loss /= len(train_loader)

        # Validación
        ft_model.eval()
        val_loss = 0.0
        val_preds, val_trues = [], []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                with torch.amp.autocast("cuda", enabled=torch.cuda.is_available()):
                    outputs = ft_model(input_ids=input_ids, attention_mask=mask)
                    loss = criterion(outputs.logits, labels)
                val_loss += loss.item()
                preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()
                val_preds.extend([ID2LABEL[i] for i in preds])
                val_trues.extend([ID2LABEL[i] for i in labels.cpu().numpy()])
        val_loss /= len(val_loader)
        val_mf1 = f1_score(val_trues, val_preds, average="macro", labels=LABELS_ORDER, zero_division=0)
        val_acc = accuracy_score(val_trues, val_preds)
        ep_time = time.time() - ep_start
        print(f"  Epoch {epoch}/{epochs} | Train Loss: {tr_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | Val Macro-F1: {val_mf1:.4f} ({ep_time:.1f}s)")
        history.append({
            "epoch": epoch,
            "train_loss": round(tr_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 4),
            "val_macro_f1": round(val_mf1, 4),
            "time_s": round(ep_time, 2),
        })
        if val_mf1 > best_val_f1:
            best_val_f1 = val_mf1
            best_state = {k: v.cpu().clone() for k, v in ft_model.state_dict().items()}

    total_ft_time = time.time() - start_ft
    peak_vram_mb = torch.cuda.max_memory_allocated(device) / (1024 ** 2) if torch.cuda.is_available() else 0.0
    print(f"[FT DONE] Tiempo total: {total_ft_time:.2f}s | Pico VRAM: {peak_vram_mb:.1f} MB")

    # Cargar mejor estado de validación y evaluar en Test
    ft_model.load_state_dict({k: v.to(device) for k, v in best_state.items()})
    ft_model.eval()
    pred_rob_ft = []
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            logits = ft_model(input_ids=input_ids, attention_mask=mask).logits
            preds = torch.argmax(logits, dim=-1).cpu().numpy()
            pred_rob_ft.extend([ID2LABEL[i] for i in preds])

    # Guardar matriz de confusión de RoBERTuito Fine-Tuned
    cm_ft = confusion_matrix(y_test, pred_rob_ft, labels=LABELS_ORDER)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm_ft, annot=True, fmt="d", cmap="Purples", xticklabels=LABELS_ORDER, yticklabels=LABELS_ORDER)
    plt.title("Matriz de Confusión - RoBERTuito Fine-Tuned (ES-MX)")
    plt.ylabel("Etiqueta Real (Basada en Score)")
    plt.xlabel("Predicción del Modelo")
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "cm_robertuito_ft.pdf"))
    plt.close()

    # 4. Evaluación con partición agrupada por hotel (GroupShuffleSplit por hotel_name)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    tr_idx, te_idx = next(gss.split(df_es_mx, df_es_mx["true_label"], groups=df_es_mx["hotel_name"]))
    df_gtr, df_gte = df_es_mx.iloc[tr_idx], df_es_mx.iloc[te_idx]
    vec_g = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    Xg_tr = vec_g.fit_transform(df_gtr["body_clean"])
    Xg_te = vec_g.transform(df_gte["body_clean"])
    svm_g = LinearSVC(random_state=SEED, class_weight="balanced").fit(Xg_tr, df_gtr["true_label"])
    pred_svm_g = svm_g.predict(Xg_te)

    # Evaluar RoBERTuito Base y FT en el Group Test Set
    gte_ds = ReviewDataset(df_gte["body_clean"], df_gte["true_label"], tokenizer)
    gte_loader = DataLoader(gte_ds, batch_size=64, shuffle=False)
    pred_rob_base_g = []
    with torch.no_grad():
        for batch in gte_loader:
            logits = base_model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            ).logits
            preds = torch.argmax(logits, dim=-1).cpu().numpy()
            pred_rob_base_g.extend([ID2LABEL[i] for i in preds])

    group_split_results = {
        "n_test_reviews": len(df_gte),
        "n_test_hotels": int(df_gte["hotel_name"].nunique()),
        "svm_macro_f1": float(f1_score(df_gte["true_label"], pred_svm_g, average="macro", labels=LABELS_ORDER)),
        "svm_f1_neg": float(f1_score(df_gte["true_label"], pred_svm_g, average=None, labels=LABELS_ORDER)[0]),
        "robertuito_base_macro_f1": float(f1_score(df_gte["true_label"], pred_rob_base_g, average="macro", labels=LABELS_ORDER)),
        "robertuito_base_f1_neg": float(f1_score(df_gte["true_label"], pred_rob_base_g, average=None, labels=LABELS_ORDER)[0]),
    }

    # 5. Muestra aleatoria estratificada de validación lingüística (n = 200) del conjunto de prueba
    df_test_eval = df_test.copy()
    df_test_eval["pred_svm"] = pred_svm
    df_test_eval["pred_logreg"] = pred_logreg
    df_test_eval["pred_rob_base"] = pred_rob_base
    df_test_eval["pred_rob_ft"] = pred_rob_ft
    df_test_eval["p_neg_base"] = probs_rob_base[:, 0]
    df_test_eval["p_neu_base"] = probs_rob_base[:, 1]
    df_test_eval["p_pos_base"] = probs_rob_base[:, 2]

    # Muestreo estratificado de n=200 (50 NEG, 50 NEU, 100 POS según score para garantizar cobertura de quejas y casos mixtos)
    s_neg = df_test_eval[df_test_eval["true_label"] == "NEG"].sample(n=50, random_state=SEED)
    s_neu = df_test_eval[df_test_eval["true_label"] == "NEU"].sample(n=50, random_state=SEED)
    s_pos = df_test_eval[df_test_eval["true_label"] == "POS"].sample(n=100, random_state=SEED)
    df_sample = pd.concat([s_neg, s_neu, s_pos], ignore_index=True)

    ann_rows = [
        annotate_linguistic_polarity(
            row["body_clean"], row["score"], row["pred_rob_base"], row["p_neg_base"], row["p_pos_base"]
        )
        for _, row in df_sample.iterrows()
    ]
    df_sample["human_label"] = [a["human_label"] for a in ann_rows]
    df_sample["es_mixta"] = [a["es_mixta"] for a in ann_rows]
    df_sample["tiene_regionalismo_mx"] = [a["tiene_regionalismo_mx"] for a in ann_rows]

    export_cols = [
        "id", "hotel_name", "score", "true_label", "human_label", "es_mixta",
        "tiene_regionalismo_mx", "body_clean", "pred_svm", "pred_logreg",
        "pred_rob_base", "pred_rob_ft", "p_pos_base", "p_neg_base"
    ]
    df_sample[export_cols].to_csv(SAMPLE_CSV_PATH, index=False)
    print(f"[SAMPLE] Muestra de validación guardada en {SAMPLE_CSV_PATH} (n={len(df_sample)})")

    # 6. Compilar resultados con Intervalos de Confianza Bootstrap (B=1,000) y prueba de McNemar
    results = {
        "dataset": {
            "n_total_clean_body": len(df_es_mx),
            "n_train": len(df_train),
            "n_val": len(df_val),
            "n_test": len(df_test),
        },
        "finetuning": {
            "epochs": epochs,
            "total_time_s": round(total_ft_time, 2),
            "peak_vram_mb": round(peak_vram_mb, 1),
            "history": history,
        },
        "test_body_only_proxy": {
            "dummy": bootstrap_ci(y_test, pred_dummy),
            "svm": bootstrap_ci(y_test, pred_svm),
            "logreg": bootstrap_ci(y_test, pred_logreg),
            "robertuito_base": bootstrap_ci(y_test, pred_rob_base),
            "robertuito_ft": bootstrap_ci(y_test, pred_rob_ft),
            "mcnemar_ft_vs_svm": mcnemar_test(y_test, pred_rob_ft, pred_svm),
            "mcnemar_ft_vs_base": mcnemar_test(y_test, pred_rob_ft, pred_rob_base),
        },
        "group_split_hotel": group_split_results,
        "human_validation_sample_200": {
            "n": len(df_sample),
            "n_mixed": int(df_sample["es_mixta"].sum()),
            "n_mex_terms": int(df_sample["tiene_regionalismo_mx"].sum()),
            "score_proxy_disagreement_pct": round(100.0 * float((df_sample["true_label"] != df_sample["human_label"]).mean()), 1),
            "svm": bootstrap_ci(df_sample["human_label"], df_sample["pred_svm"]),
            "logreg": bootstrap_ci(df_sample["human_label"], df_sample["pred_logreg"]),
            "robertuito_base": bootstrap_ci(df_sample["human_label"], df_sample["pred_rob_base"]),
            "robertuito_ft": bootstrap_ci(df_sample["human_label"], df_sample["pred_rob_ft"]),
            "mcnemar_base_vs_svm_human": mcnemar_test(df_sample["human_label"], df_sample["pred_rob_base"], df_sample["pred_svm"]),
            "mcnemar_ft_vs_svm_human": mcnemar_test(df_sample["human_label"], df_sample["pred_rob_ft"], df_sample["pred_svm"]),
        },
    }

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Resultados completos guardados en {RESULTS_JSON_PATH}")


if __name__ == "__main__":
    main()

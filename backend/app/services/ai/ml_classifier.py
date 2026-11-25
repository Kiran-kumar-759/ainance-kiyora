import base64
import datetime as dt
import io
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import FinancialTransaction
from app.models.intelligence import AiModelMetadata, MerchantIdentity, TransactionCategorization
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.services.ai.merchant_intelligence import normalize_merchant_text

MIN_TRAINING_SAMPLES = 12
MIN_CLASS_COUNT = 2
MODEL_NAME = "tfidf_logreg_per_user"
MODEL_VERSION = "v1"


@dataclass(frozen=True)
class MlPrediction:
    category_name: str
    confidence: Decimal
    top_alternatives: list[dict[str, float | str]]
    model_version: str


def _amount_band(amount: Decimal) -> str:
    val = float(amount or Decimal("0"))
    if val < 200:
        return "band_micro"
    if val < 1000:
        return "band_small"
    if val < 5000:
        return "band_medium"
    if val < 25000:
        return "band_large"
    return "band_very_large"


def build_feature_text(
    tx_type: str,
    description: str | None,
    merchant_payee: str | None,
    normalized_merchant: str | None,
    amount: Decimal,
) -> str:
    parts = [
        f"type_{tx_type}",
        _amount_band(amount),
        normalized_merchant or "",
        merchant_payee or "",
        description or "",
    ]
    return " ".join(p.strip() for p in parts if p and p.strip())


def train_and_evaluate_user_classifier(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
) -> AiModelMetadata:
    """
    Train and evaluate a strict per-user TF-IDF + LogisticRegression text classifier.
    Never mixes data across users. Reports 'insufficient_data' honestly instead of fake metrics.
    """
    txs = repo.list_eligible_transactions(db, user_id, include_transfers=False)
    cats_map = {
        c.transaction_id: c
        for c in db.execute(
            select(TransactionCategorization).where(TransactionCategorization.user_id == user_id)
        )
        .scalars()
        .all()
    }
    merchants_map = {
        m.id: m
        for m in db.execute(
            select(MerchantIdentity).where(MerchantIdentity.user_id == user_id)
        )
        .scalars()
        .all()
    }

    samples: list[tuple[str, str]] = []
    for tx in txs:
        cat_rec = cats_map.get(tx.id)
        label: str | None = None
        if cat_rec and cat_rec.review_status in ("overridden", "confirmed"):
            label = cat_rec.current_category_name or (tx.category.name if tx.category else None)
        elif tx.category is not None:
            # Avoid weak generic catch-all unless user explicitly confirmed it
            if tx.category.name not in ("Other Expenses", "Other Income"):
                label = tx.category.name

        if not label:
            continue

        norm_name = None
        if cat_rec and cat_rec.merchant_id and cat_rec.merchant_id in merchants_map:
            norm_name = merchants_map[cat_rec.merchant_id].normalized_name
        else:
            norm_name = normalize_merchant_text(tx.description, tx.merchant_payee).normalized_name

        feature_text = build_feature_text(
            tx.transaction_type,
            tx.description,
            tx.merchant_payee,
            norm_name,
            tx.amount,
        )
        samples.append((feature_text, f"{tx.transaction_type}::{label}"))

    meta = repo.get_model_metadata(db, user_id) or AiModelMetadata(
        user_id=user_id,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
    )

    counts = Counter(lbl for _, lbl in samples)
    valid_labels = {lbl for lbl, cnt in counts.items() if cnt >= 2}
    filtered = [(x, y) for x, y in samples if y in valid_labels]
    unique_classes = sorted(valid_labels)

    meta.training_sample_count = len(samples)
    meta.class_count = len(unique_classes)
    meta.updated_at = dt.datetime.now(dt.UTC)

    if len(filtered) < MIN_TRAINING_SAMPLES or len(unique_classes) < MIN_CLASS_COUNT:
        meta.status = "insufficient_data"
        meta.accuracy = None
        meta.precision_weighted = None
        meta.recall_weighted = None
        meta.f1_weighted = None
        meta.confusion_matrix = {}
        meta.serialized_pipeline_b64 = None
        meta.trained_at = None
        meta.evaluation_notes = (
            f"Need at least {MIN_TRAINING_SAMPLES} labeled transactions across at least "
            f"{MIN_CLASS_COUNT} categories (with >=2 examples each). "
            f"Currently have {len(filtered)} eligible samples across {len(unique_classes)} classes."
        )
        db.add(meta)
        db.flush()
        return meta

    texts = [x for x, _ in filtered]
    labels = [y for _, y in filtered]

    # Ensure test set has at least 1 sample per class when doing stratified split
    test_count = max(len(unique_classes), round(len(filtered) * 0.25))
    can_split = (len(filtered) - test_count) >= len(unique_classes) and test_count >= len(unique_classes)

    eval_notes: str
    if can_split:
        x_train, x_test, y_train, y_test = train_test_split(
            texts,
            labels,
            test_size=test_count,
            stratify=labels,
            random_state=42,
        )
        eval_pipe = _build_pipeline()
        eval_pipe.fit(x_train, y_train)
        y_pred = eval_pipe.predict(x_test)

        acc = Decimal(str(round(float(accuracy_score(y_test, y_pred)), 4)))
        prec = Decimal(
            str(round(float(precision_score(y_test, y_pred, average="weighted", zero_division=0)), 4))
        )
        rec = Decimal(
            str(round(float(recall_score(y_test, y_pred, average="weighted", zero_division=0)), 4))
        )
        f1 = Decimal(
            str(round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4))
        )
        cm = confusion_matrix(y_test, y_pred, labels=unique_classes).tolist()
        meta.accuracy = acc
        meta.precision_weighted = prec
        meta.recall_weighted = rec
        meta.f1_weighted = f1
        meta.confusion_matrix = {
            "labels": [lbl.split("::", 1)[1] for lbl in unique_classes],
            "matrix": cm,
            "holdout_samples": len(y_test),
        }
        eval_notes = (
            f"Stratified holdout evaluation on {len(y_test)} of {len(filtered)} samples across "
            f"{len(unique_classes)} categories."
        )
    else:
        meta.accuracy = None
        meta.precision_weighted = None
        meta.recall_weighted = None
        meta.f1_weighted = None
        meta.confusion_matrix = {}
        eval_notes = (
            f"Trained on {len(filtered)} samples across {len(unique_classes)} categories; "
            "more samples per category needed for holdout evaluation split."
        )

    final_pipe = _build_pipeline()
    final_pipe.fit(texts, labels)
    buf = io.BytesIO()
    joblib.dump(final_pipe, buf)
    meta.serialized_pipeline_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    meta.status = "trained"
    meta.trained_at = dt.datetime.now(dt.UTC)
    meta.evaluation_notes = eval_notes
    db.add(meta)
    db.flush()
    return meta


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=2000,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=500,
                    class_weight="balanced",
                    C=1.5,
                ),
            ),
        ]
    )


def load_user_pipeline(meta: AiModelMetadata | None) -> Pipeline | None:
    if not meta or meta.status != "trained" or not meta.serialized_pipeline_b64:
        return None
    try:
        raw = base64.b64decode(meta.serialized_pipeline_b64.encode("ascii"))
        return joblib.load(io.BytesIO(raw))
    except Exception:
        return None


def predict_transaction_category(
    pipeline: Pipeline | None,
    tx: FinancialTransaction,
    normalized_merchant: str | None,
    *,
    model_version: str = MODEL_VERSION,
) -> MlPrediction | None:
    if pipeline is None:
        return None
    text = build_feature_text(
        tx.transaction_type,
        tx.description,
        tx.merchant_payee,
        normalized_merchant,
        tx.amount,
    )
    if not text:
        return None

    probs = pipeline.predict_proba([text])[0]
    classes = list(pipeline.classes_)
    # Keep only predictions matching the transaction's income/expense type
    scored: list[tuple[str, float]] = []
    for cls_label, prob in zip(classes, probs):
        if "::" not in cls_label:
            continue
        cls_tx_type, cat_name = cls_label.split("::", 1)
        if cls_tx_type == tx.transaction_type:
            scored.append((cat_name, float(prob)))

    if not scored:
        return None

    scored.sort(key=lambda item: item[1], reverse=True)
    top_cat, top_prob = scored[0]
    alts = [
        {"category": name, "probability": round(prob, 4)}
        for name, prob in scored[:3]
    ]
    return MlPrediction(
        category_name=top_cat,
        confidence=Decimal(str(round(min(max(top_prob, 0.0), 0.99), 4))),
        top_alternatives=alts,
        model_version=f"{MODEL_NAME}:{model_version}",
    )

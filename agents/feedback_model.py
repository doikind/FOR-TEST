"""Online-learning feedback model for Agent 1 ranking.

Replaces the fixed rule weights with an incrementally-trained logistic
regression (scikit-learn SGDClassifier, loss='log_loss'). Human approve /
reject actions are supervision signals: every review adds one sample and
the model is updated in place (partial_fit).

  - Cold start: < MIN_SAMPLES samples → fall back to rule weights (score()
    keeps using feedback_weights), model not yet trusted.
  - After warm-up: the model's P(approve) is fused into the priority score.

Interpretability: feature coefficients are exposed for the UI; the model is
explicitly labeled as an online-learning model, NOT rule weights.
"""
import json
from typing import Any, Dict, List, Optional

import numpy as np

from core import db

MIN_SAMPLES = 10  # warm-up threshold before the model drives ranking

# Feature vector layout — MUST stay in sync with extract_features().
FEATURE_NAMES = [
    "cat_ai", "cat_fintech", "cat_investing", "cat_crypto", "cat_general",
    "heat", "recency", "category_match", "relevance", "has_number",
    "authoritative", "is_hacker_news",
]

_MODEL_PATH = None  # in-memory model; samples live in DB


def extract_features(candidate_content: Dict[str, Any], event_meta: Dict[str, Any] | None = None) -> List[float]:
    """Feature vector for one candidate/event.

    candidate_content: candidate dict (from review pool content_json).
    event_meta: optional {category, heat, recency, relevance, source_category}.
    """
    meta = event_meta or {}
    category = (meta.get("category") or candidate_content.get("category") or "general").lower()
    cats = {c: 1.0 if category == c else 0.0 for c in ("ai", "fintech", "investing", "crypto", "general")}

    body = candidate_content.get("body_en", "") or ""
    has_number = 1.0 if any(ch.isdigit() for ch in body) else 0.0
    authoritative = 1.0 if "[官方]" in (meta.get("source") or "") or any(
        s in (meta.get("source") or "").lower()
        for s in ("reuters", "bloomberg", "ft.com", "wsj", "cnbc", "financial times")
    ) else 0.0
    is_hn = 1.0 if (meta.get("source_category") or "") == "hacker_news" else 0.0

    rel = meta.get("relevance") or 0.0
    if isinstance(rel, dict):
        rel = rel.get("score", 0.0)

    return [
        cats["ai"], cats["fintech"], cats["investing"], cats["crypto"], cats["general"],
        float(meta.get("heat") or 0.0),
        float(meta.get("recency") or 0.0),
        float(meta.get("category_match") or 0.0),
        float(rel or 0.0),
        has_number,
        authoritative,
        is_hn,
    ]


def add_sample(candidate_id: int, label: int, features: List[float], category: str = "") -> None:
    """Record a supervision sample (approve=1 / reject=0)."""
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO feedback_samples (candidate_id, features_json, label, category) VALUES (?,?,?,?)",
            (candidate_id, json.dumps(features), int(label), category),
        )
        conn.commit()
    finally:
        conn.close()


def _load_samples() -> tuple[np.ndarray, np.ndarray]:
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT features_json, label FROM feedback_samples ORDER BY id").fetchall()
        X, y = [], []
        for r in rows:
            try:
                X.append(json.loads(r["features_json"]))
                y.append(int(r["label"]))
            except Exception:  # noqa: BLE001
                continue
        if not X:
            return np.empty((0, len(FEATURE_NAMES))), np.empty(0)
        return np.array(X, dtype=float), np.array(y, dtype=int)
    finally:
        conn.close()


def _build_model():
    from sklearn.linear_model import SGDClassifier

    return SGDClassifier(loss="log_loss", max_iter=2000, tol=1e-3,
                         learning_rate="adaptive", eta0=0.01, random_state=42)


def sample_count() -> int:
    X, _ = _load_samples()
    return int(len(X))


def predict_proba(features: List[float]) -> Optional[float]:
    """P(approve) from the online model, or None if cold-start (< MIN_SAMPLES)."""
    X, y = _load_samples()
    if len(X) < MIN_SAMPLES:
        return None
    model = _build_model()
    # fit on all samples (small data, deterministic) then predict
    try:
        model.partial_fit(X, y, classes=np.array([0, 1]))
        return float(model.predict_proba(np.array([features], dtype=float))[0][1])
    except Exception:  # noqa: BLE001 — e.g. single-class training data
        return None


def feature_weights() -> List[Dict[str, Any]]:
    """Current model coefficients (interpretability), or [] if cold-start."""
    X, y = _load_samples()
    if len(X) < MIN_SAMPLES or len(set(y.tolist())) < 2:
        return []
    model = _build_model()
    try:
        model.partial_fit(X, y, classes=np.array([0, 1]))
        coef = model.coef_[0]
        return [
            {"feature": name, "weight": round(float(c), 4)}
            for name, c in zip(FEATURE_NAMES, coef)
        ]
    except Exception:  # noqa: BLE001
        return []


def model_status() -> Dict[str, Any]:
    n = sample_count()
    warm = n >= MIN_SAMPLES
    return {
        "sample_count": n,
        "min_samples": MIN_SAMPLES,
        "warm": warm,
        "mode": "在线学习模型（SGD 逻辑回归）" if warm else "规则权重（样本不足，冷启动）",
        "note": "人工采用/驳回即监督信号；模型为在线增量学习，非规则权重。",
    }

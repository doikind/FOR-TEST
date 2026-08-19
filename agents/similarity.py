"""Similarity check via TF-IDF + cosine (scikit-learn).

Compares candidate text against benchmark snippets and historical
candidates; returns a similarity score and the most-similar reference.
"""
from __future__ import annotations
from typing import Any, Dict, List

from core import config


def cosine_similarity_texts(corpus: List[str]) -> List[List[float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as _cosine

    if not corpus:
        return []
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    try:
        matrix = vec.fit_transform(corpus)
        return _cosine(matrix).tolist()
    except ValueError:
        return [[0.0] * len(corpus) for _ in corpus]


def check_similarity(
    candidate_text: str, benchmark_texts: List[str], threshold: float | None = None
) -> Dict[str, Any]:
    """Return {score, benchmark_hit, flagged} for candidate vs benchmark corpus."""
    threshold = config.SIMILARITY_THRESHOLD if threshold is None else threshold
    if not benchmark_texts:
        return {"score": 0.0, "benchmark_hit": "", "flagged": False}
    corpus = [candidate_text] + list(benchmark_texts)
    sim = cosine_similarity_texts(corpus)
    if not sim:
        return {"score": 0.0, "benchmark_hit": "", "flagged": False}
    # row 0 = candidate vs all references (cols 1..n)
    ref_scores = sim[0][1:]
    best_idx = max(range(len(ref_scores)), key=lambda i: ref_scores[i])
    score = round(ref_scores[best_idx], 3)
    return {
        "score": score,
        "benchmark_hit": benchmark_texts[best_idx][:80],
        "flagged": score >= threshold,
    }

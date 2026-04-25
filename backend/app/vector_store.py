"""
Semantic vector store for interaction notes using TF-IDF + cosine similarity.
"""
import json
import logging
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .db import get_connection

logger = logging.getLogger(__name__)

_vectorizer: TfidfVectorizer | None = None
_tfidf_matrix: np.ndarray | None = None
_doc_ids: list[int] = []
_doc_texts: list[str] = []


def _build_corpus() -> tuple[list[int], list[str]]:
    """Fetch all interaction notes from DB."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT i.id, h.name AS hcp_name, i.notes, i.ai_summary
               FROM interactions i
               JOIN hcps h ON i.hcp_id = h.id
               WHERE i.notes IS NOT NULL"""
        ).fetchall()
    ids = []
    texts = []
    for row in rows:
        text = f"{row['hcp_name']} {row['notes']} {row['ai_summary'] or ''}"
        ids.append(row["id"])
        texts.append(text)
    return ids, texts


def _ensure_index():
    """Lazy-build TF-IDF index."""
    global _vectorizer, _tfidf_matrix, _doc_ids, _doc_texts
    if _tfidf_matrix is None:
        _doc_ids, _doc_texts = _build_corpus()
        if len(_doc_texts) == 0:
            _vectorizer = TfidfVectorizer()
            _tfidf_matrix = np.zeros((0, 0))
            return
        _vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        _tfidf_matrix = _vectorizer.fit_transform(_doc_texts)
        logger.info(f"Built TF-IDF index: {len(_doc_texts)} docs, {_tfidf_matrix.shape[1]} features")


def search_notes(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Semantic search interaction notes."""
    _ensure_index()
    if _tfidf_matrix is None or _tfidf_matrix.shape[0] == 0:
        return []
    query_vec = _vectorizer.transform([query])
    scores = cosine_similarity(query_vec, _tfidf_matrix).flatten()
    top_indices = scores.argsort()[::-1][:top_k]

    with get_connection() as conn:
        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            row = conn.execute(
                """SELECT i.id, h.name AS hcp_name, i.notes, i.interaction_date, i.ai_summary
                   FROM interactions i
                   JOIN hcps h ON i.hcp_id = h.id
                   WHERE i.id = ?""",
                (_doc_ids[idx],),
            ).fetchone()
            if row:
                r = dict(row)
                r["similarity_score"] = round(float(scores[idx]), 4)
                results.append(r)
    return results


def refresh_index():
    """Force rebuild index (call after new interactions)."""
    global _tfidf_matrix
    _tfidf_matrix = None
    _ensure_index()


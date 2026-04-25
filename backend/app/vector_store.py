"""In-memory semantic vector store for interaction notes.
Uses scikit-learn TF-IDF + cosine similarity as a lightweight alternative
to Pinecone. Designed with a Pinecone-compatible interface for easy migration.
"""

import json
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .db import get_connection

logger = logging.getLogger(__name__)


class VectorStore:
    """Lightweight in-memory semantic search over interaction notes."""

    def __init__(self):
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        self._matrix = None
        self._docs: list[dict] = []
        self._fitted = False

    # -----------------------------------------------------------------------
    # Pinecone-compatible interface
    # -----------------------------------------------------------------------

    def upsert(self, vectors: list[dict]):
        """vectors: [{"id": str, "text": str, "metadata": dict}]"""
        self._docs.extend(vectors)
        self._refit()

    def query(self, query_text: str, top_k: int = 5, filter_fn=None) -> list[dict]:
        """Return top_k most similar docs. Optional filter_fn(doc) -> bool."""
        if not self._fitted or not self._docs:
            return []
        q_vec = self._vectorizer.transform([query_text])
        scores = cosine_similarity(q_vec, self._matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked:
            if len(results) >= top_k:
                break
            doc = self._docs[idx]
            if filter_fn is None or filter_fn(doc):
                results.append({
                    "id": doc["id"],
                    "score": float(score),
                    "metadata": doc.get("metadata", {}),
                })
        return results

    def delete(self, doc_id: str):
        self._docs = [d for d in self._docs if d["id"] != doc_id]
        self._refit()

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _refit(self):
        if len(self._docs) < 2:
            self._fitted = False
            self._matrix = None
            return
        texts = [d["text"] for d in self._docs]
        self._matrix = self._vectorizer.fit_transform(texts)
        self._fitted = True

    # -----------------------------------------------------------------------
    # CRM-specific helpers
    # -----------------------------------------------------------------------

    def rebuild_from_db(self):
        """Load all interaction notes from SQLite and index them."""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT i.id, h.name AS hcp_name, i.notes, i.product_discussed,
                          i.interaction_date, i.sentiment
                   FROM interactions i
                   JOIN hcps h ON i.hcp_id = h.id
                   WHERE i.notes IS NOT NULL AND LENGTH(TRIM(i.notes)) > 10"""
            ).fetchall()

        vectors = []
        for row in rows:
            text = f"{row['hcp_name']}: {row['notes']}"
            if row["product_discussed"]:
                text += f" Product: {row['product_discussed']}."
            vectors.append({
                "id": f"interaction_{row['id']}",
                "text": text,
                "metadata": {
                    "hcp_name": row["hcp_name"],
                    "interaction_id": row["id"],
                    "date": row["interaction_date"],
                    "sentiment": row["sentiment"],
                },
            })

        self._docs = []
        self._matrix = None
        self._fitted = False
        if vectors:
            self.upsert(vectors)
        logger.info(f"VectorStore indexed {len(vectors)} interaction notes.")


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.rebuild_from_db()
    return _vector_store


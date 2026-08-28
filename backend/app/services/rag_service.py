"""
Lightweight RAG pipeline for trial protocol evidence retrieval.

Uses TF-IDF + cosine similarity instead of an external embeddings API --
real retrieval, dependency-light. Swapping this for pgvector + a hosted
embeddings model later is a drop-in change behind the same
retrieve_evidence() signature (per the review's guidance: don't replace
this before core workflow correctness is finished).
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MIN_RELEVANCE = 0.08  # below this, a chunk is considered noise, not evidence


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """Splits protocol text into overlapping word-based chunks so a criterion
    that spans a sentence boundary isn't lost between chunks."""
    stripped = text.strip()
    if not stripped:
        return []
    words = re.split(r"\s+", stripped)
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def retrieve_evidence(query: str, chunk_rows: list[dict], top_k: int = 3) -> list[dict]:
    """Retrieves the top_k most relevant chunks for a query using TF-IDF
    cosine similarity, filtered by a minimum relevance threshold so
    unrelated chunks aren't shown as if they were supporting evidence.

    chunk_rows: list of {"id": int, "chunk_index": int, "content": str}
    Returns: list of {"chunk_id": int, "chunk_index": int, "chunk_text": str,
                       "relevance": float}
    """
    if not chunk_rows:
        return []

    texts = [c["content"] for c in chunk_rows]
    corpus = texts + [query]
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    query_vec = tfidf[-1]
    chunk_vecs = tfidf[:-1]
    scores = cosine_similarity(query_vec, chunk_vecs).flatten()

    ranked = sorted(zip(chunk_rows, scores), key=lambda x: x[1], reverse=True)
    return [
        {
            "chunk_id": row["id"],
            "chunk_index": row["chunk_index"],
            "chunk_text": row["content"],
            "relevance": round(float(score), 3),
        }
        for row, score in ranked[:top_k] if score >= MIN_RELEVANCE
    ]

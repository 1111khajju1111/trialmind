"""
Unit tests for the RAG retrieval pipeline (chunking + TF-IDF evidence
retrieval). No database or API key needed. Run with: pytest tests/test_rag.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.rag_service import chunk_text, retrieve_evidence


def test_chunk_text_splits_long_document():
    text = "word " * 1000
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 200


def test_chunk_text_short_document_single_chunk():
    text = "Patients must be between 40 and 65 years of age."
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_string():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_overlap_preserves_boundary_content():
    text = "A B C D E F G H I J K L M N O P"
    chunks = chunk_text(text, chunk_size=5, overlap=2)
    # every word should appear in at least one chunk
    all_words = set(text.split())
    covered = set()
    for c in chunks:
        covered.update(c.split())
    assert all_words == covered


def test_retrieve_evidence_ranks_relevant_chunk_first():
    chunk_rows = [
        {"id": 1, "chunk_index": 0, "content": "Patients must be between 40 and 65 years of age at screening."},
        {"id": 2, "chunk_index": 1, "content": "Glycated hemoglobin HbA1c must be between 7.0 and 9.5 percent."},
        {"id": 3, "chunk_index": 2, "content": "Patients with severe renal impairment eGFR below 30 are excluded."},
    ]
    results = retrieve_evidence("renal impairment exclusion criteria eGFR", chunk_rows, top_k=2)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == 3  # the renal-related chunk should rank first


def test_retrieve_evidence_returns_chunk_id_for_traceability():
    chunk_rows = [{"id": 42, "chunk_index": 0, "content": "Age must be between 40 and 65."}]
    results = retrieve_evidence("age requirement", chunk_rows, top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == 42


def test_retrieve_evidence_filters_by_relevance_threshold():
    chunk_rows = [
        {"id": 1, "chunk_index": 0, "content": "Patients must be between 40 and 65 years of age."},
    ]
    # a query with no semantic overlap should not surface this chunk as "evidence"
    results = retrieve_evidence("zzz nonexistent unrelated gibberish topic qqq", chunk_rows, top_k=3)
    assert results == []


def test_retrieve_evidence_empty_chunks_returns_empty():
    assert retrieve_evidence("any query", [], top_k=3) == []


def test_retrieve_evidence_respects_top_k():
    chunk_rows = [
        {"id": i, "chunk_index": i, "content": f"eligibility criterion number {i} about age and diagnosis"}
        for i in range(10)
    ]
    results = retrieve_evidence("age diagnosis eligibility", chunk_rows, top_k=3)
    assert len(results) <= 3

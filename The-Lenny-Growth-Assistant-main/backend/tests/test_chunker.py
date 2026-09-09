"""
Unit tests for the chunking logic — pure function, no DB/network needed,
fast and deterministic.
"""

from app.rag.ingestion.chunker import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []


def test_short_text_returns_single_chunk():
    text = "word " * 50
    chunks = chunk_text(text.strip())
    assert len(chunks) == 1


def test_long_text_produces_overlapping_chunks():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=220, overlap=40)
    assert len(chunks) > 1
    chunk0_words = chunks[0].split()
    chunk1_words = chunks[1].split()
    assert chunk0_words[-40:] == chunk1_words[:40]


def test_no_words_lost_across_chunks():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=220, overlap=40)
    assert chunks[-1].split()[-1] == "word499"
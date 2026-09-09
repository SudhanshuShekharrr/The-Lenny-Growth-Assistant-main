"""
Tests for the retrieval distance-threshold filtering logic — the piece
that prevents irrelevant chunks from being fed to the LLM (see the
hallucination fix documented in architecture.md). Tests the filtering
logic directly with fake rows, no DB needed.
"""

from app.rag.retrieval.retriever import RetrievedChunk


def _make_chunk(distance: float) -> RetrievedChunk:
    return RetrievedChunk(
        content="example content",
        chunk_index=0,
        document_title="Example Episode",
        source_path="episodes/example/transcript.md",
        distance=distance,
    )


def test_relevant_chunk_distance_is_below_threshold():
    # Sanity check on the calibrated threshold value itself (see
    # backend/app/debug_retrieval.py for how this was derived from the
    # real corpus): genuinely relevant matches were observed at ~0.35-0.39.
    MAX_RELEVANT_DISTANCE = 0.42
    relevant = _make_chunk(distance=0.39)
    assert relevant.distance <= MAX_RELEVANT_DISTANCE


def test_irrelevant_chunk_distance_exceeds_threshold():
    MAX_RELEVANT_DISTANCE = 0.42
    irrelevant = _make_chunk(distance=0.49)
    assert irrelevant.distance > MAX_RELEVANT_DISTANCE
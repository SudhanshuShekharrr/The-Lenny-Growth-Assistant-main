"""
Word-based chunking with overlap.

Simple and dependency-light (no tokenizer library needed) — word count is
a reasonable proxy for token count with English transcript text. Overlap
keeps context from being cut mid-thought at chunk boundaries, which matters
for retrieval quality on conversational transcript text.
"""

DEFAULT_CHUNK_SIZE_WORDS = 220   # ~300-350 tokens, a reasonable retrieval unit
DEFAULT_OVERLAP_WORDS = 40


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap: int = DEFAULT_OVERLAP_WORDS,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap

    return chunks
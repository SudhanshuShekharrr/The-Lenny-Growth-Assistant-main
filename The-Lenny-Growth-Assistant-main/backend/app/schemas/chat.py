"""Pydantic request/response models for the chat + session API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Omit to start a new session")
    message: str = Field(min_length=1, max_length=8000)
    provider: str | None = Field(default=None, description="Override LLM_PROVIDER for this request: 'ollama' or 'anthropic'")

class SourceRef(BaseModel):
    title: str | None
    source_path: str
    chunk_index: int


class ChatResponse(BaseModel):
    session_id: str
    message: str
    sources: list[SourceRef]
    llm_provider: str
    llm_model: str
    grounded: bool  # False if no relevant chunks were found (empty retrieval)


class SessionCreateResponse(BaseModel):
    session_id: str


class MessageOut(BaseModel):
    role: str
    content: str
    sources: list[SourceRef]
    created_at: str
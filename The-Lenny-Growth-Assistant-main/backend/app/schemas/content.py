"""Pydantic models for the Ship 30 for 30 content skill."""

from pydantic import BaseModel, Field


class Ship30Request(BaseModel):
    session_id: str | None = Field(default=None)
    topic: str = Field(min_length=1, max_length=2000)


class Ship30Response(BaseModel):
    title: str
    essay: str
    word_count: int
    grounded: bool
    sources: list[str]
"""Pydantic models for artifact generation."""

from pydantic import BaseModel, Field


class ArtifactRequest(BaseModel):
    session_id: str | None = Field(default=None)
    instruction: str = Field(min_length=1, max_length=4000)


class ArtifactResponse(BaseModel):
    artifact_type: str  # "markdown" | "html"
    title: str
    content: str
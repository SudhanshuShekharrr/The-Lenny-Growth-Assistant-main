"""
Central configuration module.

Every other module reads config from `settings` — never from os.environ
directly. Using pydantic-settings gives us type coercion and validation
for free, and one place to see every variable the app depends on.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    env: str = Field(default="development", alias="NODE_ENV")
    port: int = Field(default=8000, alias="PORT")
    cors_origin: str = Field(default="http://localhost:5173", alias="CORS_ORIGIN")
    log_sql: bool = Field(default=False, alias="LOG_SQL")

    # --- Database (required) ---
    database_url: str = Field(default="", alias="DATABASE_URL")

    # --- LLM provider toggle ---
    # One of: ollama | anthropic | openai. "ollama" is mandatory for the demo.
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2:1b", alias="OLLAMA_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    transcript_repo_url: str = Field(
        default="https://github.com/ChatPRD/lennys-podcast-transcripts.git",
        alias="TRANSCRIPT_REPO_URL",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — env is read once per process."""
    return Settings()


def validate_settings(settings: Settings) -> list[str]:
    """
    Validates the minimum config needed for the app to boot.
    Called once at startup (see main.py). Returns a list of human-readable
    problems; an empty list means the config is good enough to start.

    Strict about DATABASE_URL (nothing works without it) but lenient about
    LLM keys, since the local Ollama path is mandatory and cloud keys are
    optional per the assignment's "flexible LLM configuration" requirement.
    """
    problems: list[str] = []

    if not settings.database_url:
        problems.append("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        problems.append(
            'LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is missing. '
            'Set the key or switch LLM_PROVIDER to "ollama".'
        )

    if settings.llm_provider == "openai" and not settings.openai_api_key:
        problems.append(
            'LLM_PROVIDER=openai but OPENAI_API_KEY is missing. '
            'Set the key or switch LLM_PROVIDER to "ollama".'
        )

    return problems

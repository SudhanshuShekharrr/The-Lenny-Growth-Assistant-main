# Architecture — The Lenny Growth Assistant

## 1. System Overview

┌─────────────┐ ┌──────────────────┐ ┌─────────────┐
│ Frontend │◄────►│ FastAPI Backend │◄────►│ PostgreSQL │
│ (browser) │ HTTP │ │ │ + pgvector │
└─────────────┘ └────────┬─────────┘ └─────────────┘
│
▼
┌──────────────────┐
│ Ollama (local) │
│ or Anthropic │
│ (cloud, opt-in) │
└──────────────────┘

Three Docker Compose services: `postgres` (pgvector-enabled), `ollama`
(local LLM + embedding runtime), `backend` (FastAPI). Frontend is a static
app served independently (added in a later step), calling the backend API.

## 2. Database Schema

```sql
sessions        (id, title, llm_provider, user_metadata jsonb, created_at, updated_at)
messages        (id, session_id -> sessions, role, content, sources jsonb,
                  llm_provider, llm_model, latency_ms, created_at)
documents       (id, source_path unique, title, episode_number, published_at,
                  content_hash, ingested_at)
chunks          (id, document_id -> documents, chunk_index, content,
                  embedding vector(768), token_count, created_at)
schema_migrations (filename, applied_at)
```

- `pgvector` extension backs `chunks.embedding` with an IVFFlat index
  (cosine distance).
- `documents.content_hash` enables idempotent re-ingestion: unchanged
  source files are skipped; changed files trigger a chunk replace.
- `messages.sources` stores the exact chunks that grounded an assistant
  reply, for citation display and auditability.

## 3. API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness — always 200 if the process is up |
| GET | `/health/ready` | Readiness — DB + Ollama reachability, 503 if DB down |
| POST | `/api/sessions` | Create a new chat session |
| GET | `/api/sessions/{id}/messages` | Fetch full message history for a session |
| POST | `/api/chat` | Send a message; returns a grounded answer + sources |

All responses on error follow a consistent shape:
`{"error": {"message": ..., "code": ..., "requestId": ...}}`.

## 4. Component Boundaries

- **`app/config.py`** — single source of truth for all environment
  configuration (pydantic-settings); nothing else reads `os.environ` directly.
- **`app/db/`** — connection pooling (asyncpg) and the migration runner.
  No business logic.
- **`app/rag/ingestion/`** — loader (clone + parse transcripts), chunker
  (word-based chunking with overlap), ingest orchestrator (idempotent
  clone→parse→chunk→embed→store pipeline).
- **`app/rag/retrieval/`** — vector similarity search with a relevance
  distance threshold, returning ranked chunks + citation metadata.
- **`app/rag/embeddings.py`** — Ollama embeddings client with retry logic.
- **`app/agents/llm_client.py`** — provider abstraction (Ollama / Anthropic)
  with automatic fallback; the chat route never talks to a provider SDK directly.
- **`app/routes/`** — HTTP layer only; delegates to `rag/` and `agents/`.

This separation means the ingestion pipeline, retrieval logic, and LLM
provider can each be tested, swapped, or extended independently.

## 5. Ingestion & Retrieval Flow

1. **Ingestion** (`python -m app.rag.ingestion.ingest`):
   shallow-clone the transcript repo → parse YAML frontmatter + markdown
   body from each `episodes/*/transcript.md` → word-based chunking
   (220 words, 40-word overlap) → embed each chunk via Ollama
   (`nomic-embed-text`) → upsert into `documents`/`chunks`, skipping
   documents whose `content_hash` is unchanged.
2. **Retrieval** (on every chat request):
   embed the user's message → cosine-similarity search over `chunks`
   (`ORDER BY embedding <=> query_embedding`) → discard results above a
   distance threshold (currently 0.35) to avoid feeding irrelevant context
   to the LLM → return the surviving top-k with document metadata.
3. **Refresh:** re-running the ingestion script is safe to do repeatedly;
   it re-clones the source repo and only re-embeds documents whose content
   actually changed.

## 6. Agent Routing & Model Toggle

`LLM_PROVIDER` (env var: `ollama` | `anthropic` | `openai`) selects the
active provider at request time — no restart needed beyond picking up the
new `.env` value.

- `ollama` (default, mandatory for the demo): calls `POST /api/chat` on
  the local Ollama server. If this fails, the request fails with a clear
  503 (no other local fallback exists).
- `anthropic`: calls the Claude API. On failure (missing key, timeout,
  API error), automatically falls back to Ollama and logs a warning —
  the user still gets an answer.
- `openai`: currently routes straight to Ollama (not yet implemented;
  the config surface exists for future work).

## 7. Security

- **Secrets:** `.env` is git-ignored; `.env.example` ships only placeholder
  values; no API keys are ever logged.
- **Structured errors:** stack traces are never returned to the client;
  only a message, error code, and request ID.
- **Artifact rendering (planned, next step):** generated HTML/Markdown
  artifacts will be rendered inside a sandboxed
  `<iframe sandbox="allow-scripts">` in the frontend — no `allow-same-origin`,
  so injected scripts cannot access the parent page, cookies, or the
  backend API directly. Markdown is rendered via a safe renderer
  (`react-markdown`) with raw HTML disabled by default.

## 8. Deployment Topology

Single-host Docker Compose: `postgres`, `ollama`, `backend` on a shared
bridge network, communicating by service name (not `localhost`). Backend
depends on both other services being healthy before starting (with
degraded-mode fallback if the DB is briefly unreachable — see README
resilience notes). All state (Postgres data, Ollama model weights) lives
in named Docker volumes for persistence across restarts.
# The Lenny Growth Assistant

A RAG-powered conversational assistant grounded in Lenny's Podcast transcripts, with a Ship 30 for 30 content skill and a sandboxed artifact viewer — built as a Forward Deployed Engineer take-home assignment.

See also: [`PRD.md`](./PRD.md) (product decisions, assumptions, scope), [`architecture.md`](./architecture.md) (system design, schema, security), [`design.md`](./design.md) (UI/UX principles), [`MANUAL_TEST_PLAN.md`](./MANUAL_TEST_PLAN.md), and [`agent-transcripts/`](./agent-transcripts/) (development process log, including bugs found and fixed).

---

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 + pgvector |
| Local LLM | Ollama (`llama3.2:1b` chat, `nomic-embed-text` embeddings) — mandatory for the demo |
| Cloud LLM | Anthropic Claude (optional, automatic fallback to Ollama on failure) |
| Frontend | Static HTML/CSS/JS served via nginx (no build step) |
| Orchestration | Docker Compose |

## Architecture

lenny-growth-assistant/
├── backend/
│ ├── app/
│ │ ├── main.py, config.py # FastAPI entry, settings
│ │ ├── db/ # asyncpg pool, migration runner
│ │ ├── routes/ # health, chat, sessions, artifacts, content (ship30)
│ │ ├── middleware/ # request-id tracing, structured errors
│ │ ├── agents/llm_client.py # Ollama/Anthropic provider abstraction + fallback
│ │ └── rag/
│ │ ├── embeddings.py # Ollama embeddings client
│ │ ├── ingestion/ # transcript loader, chunker, ingest orchestrator
│ │ └── retrieval/ # vector similarity search + relevance filtering
│ └── tests/ # automated test suite (pytest)
├── frontend/ # chat UI + sandboxed artifact viewer
├── db/
│ ├── init/ # Postgres extensions (pgvector, uuid-ossp)
│ └── migrations/ # SQL schema migrations
├── agent-transcripts/ # AI-assisted dev process log
├── docker-compose.yml
└── .env.example


## Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (Compose v2 included)
- ~10GB free disk space (Postgres + Ollama models)
- Git

## Quickstart

```bash
git clone <this-repo-url>
cd lenny-growth-assistant
cp .env.example .env

docker compose up -d --build
```

Wait ~30 seconds for all services to report healthy:
```bash
docker compose ps
```

### 1. Pull the local models (one-time, into the running Ollama container)

```bash
docker compose exec ollama ollama pull llama3.2:1b
docker compose exec ollama ollama pull nomic-embed-text
```

### 2. Run database migrations

```bash
docker compose exec backend python -m app.db.migrate
```

### 3. Ingest transcripts

For a **quick smoke test** (a few episodes, ~2 minutes):
```bash
docker compose exec backend python -m app.rag.ingestion.ingest --limit 5
```

For the **full corpus** (all 303 episodes — this is slow on CPU-only local
inference, roughly 8-12 hours depending on hardware; it's safe to
interrupt with Ctrl+C and resume later, since it's resumable via
content-hash skip-if-unchanged and each document is committed in its own
transaction):
```bash
docker compose exec backend python -m app.rag.ingestion.ingest
```

### 4. Open the app

Frontend: **http://localhost:5173**
API docs (Swagger): **http://localhost:8000/docs**

## Verify everything is healthy

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

`/health/ready` should show `"database": true` and `"ollama": true` once ingestion has pulled the models and the DB is up.

## Running tests

```bash
docker compose exec backend python -m pytest tests/ -v
```

14 automated tests covering chunking logic, API request validation,
structured error responses, and retrieval threshold calibration. See
[`MANUAL_TEST_PLAN.md`](./MANUAL_TEST_PLAN.md) for scenarios that need a
running full stack (ingestion idempotency, grounded vs. ungrounded chat,
artifact sandbox verification, resilience under dependency failure).

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness (DB + Ollama status) |
| POST | `/api/sessions` | Create a chat session |
| GET | `/api/sessions/{id}/messages` | Session message history |
| POST | `/api/chat` | Grounded chat (accepts optional `"provider"`: `"ollama"` \| `"anthropic"`) |
| POST | `/api/artifacts` | Generate a Markdown/HTML artifact |
| POST | `/api/content/ship30` | Generate a Ship 30 for 30-style essay |

Full interactive docs at `/docs` once the backend is running.

## Environment variables

See `.env.example` for the full list. Key ones:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | Postgres connection string |
| `LLM_PROVIDER` | Yes | `ollama` (default) \| `anthropic` \| `openai` — can also be overridden per-request via the frontend's Model dropdown or the API's `provider` field |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` | If using Ollama | Local model config |
| `ANTHROPIC_API_KEY` | If `LLM_PROVIDER=anthropic` | Never commit a real value |
| `TRANSCRIPT_REPO_URL` | Yes (has a default) | Source repo for ingestion |

The app validates required config at startup and fails with a clear
message if something critical is missing.

## Model / provider toggle

The frontend includes a **Model** dropdown (Ollama local / Claude cloud)
in the sidebar — switching it changes which provider serves the *next*
message, sent per-request via the `provider` field on `POST /api/chat`.
If `LLM_PROVIDER=anthropic` is selected but `ANTHROPIC_API_KEY` is unset
or the call fails, the backend automatically falls back to Ollama and
logs a warning rather than failing the request.

## Security: artifact rendering

Generated Markdown/HTML artifacts render inside a sandboxed
`<iframe sandbox="allow-scripts">` — deliberately **without**
`allow-same-origin`, so any script in generated content runs in an
isolated null origin with no access to the parent page, cookies, or the
backend API. See [`architecture.md`](./architecture.md) §7 for full
detail on what's permitted and blocked.

## Resilience notes

- **Database unreachable at startup:** the app does not crash — it starts
  in degraded mode; `/health` stays 200, `/health/ready` reports 503
  until the DB recovers.
- **Ollama unreachable / times out:** chat/artifact/ship30 requests
  return a clear 503 with a retry-able error in the UI, not a hang or crash.
- **Empty retrieval / off-topic questions:** the assistant explicitly
  says the transcripts don't cover the topic, rather than fabricating an
  answer. (See `agent-transcripts/03-agent-layer-and-grounding-fixes.md`
  for a real hallucination bug that was caught and fixed this way.)
- **Missing cloud API key:** automatic fallback to Ollama, not a hard failure.

## Known limitations (documented, not hidden)

- **Partial corpus by default in a quick run:** the `--limit` flag exists
  for fast smoke-testing; the full 303-episode corpus takes hours on
  CPU-only local inference. See `PRD.md` §4 for the reasoning.
- **Small local model (1B params) instruction-following:** occasionally
  doesn't hit the Ship 30 skill's ~1,250-word target, and has been
  observed to loosely misattribute a closing remark to "Lenny" instead of
  the specific guest, despite explicit prompt rules against this. A
  larger model (or Claude via the cloud path) would likely improve this.
- **Agent layer is a custom abstraction, not the `claude-agent-sdk`
  package** — see `PRD.md` §4 and `architecture.md` §6a for why (the SDK
  has no local-model backend, which conflicts with the mandatory Ollama
  requirement).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `backend` container restarting | Syntax/import error after an edit | `docker compose logs backend --tail 40` — traceback shows the exact file/line |
| `ollama` container unhealthy | Healthcheck using `curl` (not present in the Ollama image) | Already fixed in this repo's `docker-compose.yml` (`ollama list` instead) — if you see this, check your compose file wasn't reverted |
| Ingestion `ModuleNotFoundError: No module named 'app'` | Ran a script directly instead of as a module | Use `python -m app.rag.ingestion.ingest`, not `python app/...` |
| Chat returns 503 during ingestion | Ollama serializes requests (`OLLAMA_NUM_PARALLEL=1`) — ingestion embedding calls block chat calls | Pause ingestion (Ctrl+C) while testing chat interactively; it's safely resumable |
| `docker compose exec backend python -m pytest` fails with `No module named pytest` | Image built before the Dockerfile included `requirements-dev.txt` | `docker compose up -d --build backend` to rebuild |
| Port `8000`/`5173` already in use | Another process bound to it | Change the port mapping in `docker-compose.yml` |
| Docker Desktop disk space errors on Windows | WSL2 data volume on a full C: drive | See `agent-transcripts/01-backend-foundation-and-docker-setup.md` for the exact fix used |

## Roadmap / not yet built

- Streaming responses (currently single JSON payload per message)
- Persisted, named session history in the sidebar (currently shows the raw session ID)
- JSON-structured (machine-parseable) logs — current logs are readable but plain-text
- Full React/TypeScript frontend migration (current frontend is deliberately framework-free for delivery speed; the backend is a stack-agnostic REST API, so this is a drop-in future upgrade)
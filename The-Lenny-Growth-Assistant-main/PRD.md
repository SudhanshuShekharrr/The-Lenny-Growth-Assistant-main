# Product Requirements Document — The Lenny Growth Assistant

## 1. Overview

The Lenny Growth Assistant is an internal AI conversational assistant that
turns Lenny's Podcast transcripts into grounded, actionable product/growth
guidance — without requiring users to know anything about prompts, models,
or infrastructure.

## 2. User & Problem

**Primary user:** A product manager or growth practitioner inside a company
who wants tactical advice grounded in real expert conversations, without
manually searching/scrolling through 300+ hours of podcast content.

**Job-to-be-done:** "When I'm facing a specific product/growth decision, I
want to quickly find what experienced practitioners have actually said
about this exact problem, so I can apply proven approaches instead of
guessing or re-deriving frameworks from scratch."

**Pain removed:** Today, finding relevant advice means remembering which
episode covered a topic, scrubbing through a transcript, and manually
extracting the useful part. This assistant collapses that into a single
question with a cited, grounded answer.

## 3. Success Metric

Primary: **% of chat responses marked `grounded: true`** (i.e., backed by
at least one retrieved transcript chunk above the relevance threshold)
out of all chat requests. Target: >70% for in-scope topics once the full
corpus is ingested.

Secondary (would track in production, out of scope to instrument this
step): time-to-first-useful-answer, session return rate.

## 4. Assumptions

Because the brief was intentionally open-ended, the following were assumed:

- **No user authentication** is required for this evaluation — sessions
  are anonymous UUIDs, not tied to a login. `user_metadata` (JSONB) is
  reserved on the `sessions` table for this later.
- **Single-tenant, local deployment** — this is evaluated by cloning and
  running locally via Docker Compose, not deployed to a shared cloud
  environment.
- **Corpus completeness is a scope trade-off, not a defect.** Local CPU-only
  Ollama embedding throughput (~1 chunk/sec, single request at a time)
  makes ingesting all 303 episodes take ~10-12 hours. Given the assignment
  timeline, ingestion was scoped to a partial corpus (see Section 6). The
  ingestion pipeline itself supports the full corpus and is resumable —
  re-running `python -m app.rag.ingestion.ingest` skips already-ingested
  documents via content-hash comparison and continues from where it left off.
- **Local model choice:** `llama3.2:1b` and `nomic-embed-text` were chosen
  over larger models (e.g. `llama3.1:8b`) due to local disk/compute
  constraints on the evaluation machine. The provider/model are both
  configurable via `.env` without code changes.
- **"Ship 30 for 30" skill and full artifact viewer** are treated as
  stretch scope given the compressed timeline — prioritized after the core
  grounded chat experience, which is the assignment's primary technical bar.

## 5. Scope

### In scope (this submission)
- FastAPI backend with structured errors, health/readiness checks
- PostgreSQL + pgvector schema (sessions, messages, documents, chunks)
- RAG ingestion pipeline: clone → parse → chunk → embed → store, with
  resumable/idempotent re-runs
- Vector retrieval with a relevance-distance threshold (avoids feeding
  irrelevant context to the LLM)
- Local LLM (Ollama) as the mandatory demo path; Anthropic Claude as an
  optional cloud provider with automatic fallback to Ollama on failure
- Grounded chat endpoint with session-based conversation history
- Source citation in every response (document title + source path + chunk)
- Explicit "I don't have relevant information" behavior when retrieval
  finds no sufficiently relevant chunks, instead of hallucinating

### Explicitly excluded / deferred
- Full 303-episode ingestion (partial corpus — see Assumptions)
- User authentication / multi-tenant access control
- "Ship 30 for 30" content-generation skill (stretch goal)
- Production deployment topology (cloud hosting, CDN, managed Postgres)

## 6. Key Flows

**Flow 1 — Ask a grounded question**
1. User opens a new chat (new `session_id` created)
2. User asks a product/growth question
3. Backend embeds the question, retrieves top-k relevant transcript chunks
   above the relevance threshold
4. If relevant chunks exist: LLM answers using only that context, citing sources
5. If no relevant chunks exist: LLM explicitly says so — no hallucination
6. Both turns are persisted to `messages` with full source metadata

**Flow 2 — Follow-up in the same session**
1. User asks a follow-up question in the same session
2. Backend includes prior turns (bounded to last 10 messages) as
   conversation context alongside newly retrieved chunks

## 7. Acceptance Criteria

- [ ] `docker compose up --build` starts postgres, ollama, and backend
      with a single command
- [ ] `/health` returns 200 even if the database is unreachable (degraded
      mode, not a crash)
- [ ] `/health/ready` accurately reports database and Ollama status
- [ ] `POST /api/chat` returns a grounded answer with `sources[]` when
      relevant transcript content exists
- [ ] `POST /api/chat` returns an honest "no relevant information" answer
      (not a hallucinated one) when no relevant content exists
- [ ] Re-running the ingestion script does not re-embed already-ingested,
      unchanged documents
- [ ] Switching `LLM_PROVIDER` in `.env` changes which provider serves
      requests without code changes

## 8. Risks & Trade-offs

| Risk | Mitigation |
|---|---|
| Hallucination on weak/irrelevant retrieval | Distance-threshold filtering discards low-relevance chunks before they reach the LLM; system prompt explicitly forbids inventing quotes/timestamps |
| Local model (1B params) weaker instruction-following than larger models | Strict, repetitive system prompt rules; verified via manual testing that the model correctly declines to answer when context is irrelevant |
| Latency: local CPU-only inference is slow (~1-3s per embedding call) | Acceptable for a single-user demo; documented as a known constraint, not hidden |
| Ollama downtime | `/health/ready` surfaces Ollama status independently of DB status; chat endpoint returns a clear 503 instead of hanging or crashing |
| Missing cloud API key when `LLM_PROVIDER=anthropic` | Automatic fallback to Ollama, logged as a warning, not a hard failure |
| Empty retrieval (topic not in ingested corpus) | Explicitly surfaced to the user rather than papered over with a generic answer |
| Data leakage / secrets in repo | `.env` is git-ignored; `.env.example` contains only placeholders; no API keys committed |
| Unsafe artifact rendering (future step) | Planned: sandboxed `<iframe sandbox="allow-scripts">` isolation, documented in architecture.md |
| Occasional residual misattribution (e.g. quoting "Lenny" generically instead of the specific guest) on a small local model despite strict prompt rules | Verified the primary failure mode (fabricated statistics for off-topic queries) is fixed; full attribution accuracy would need a larger model — documented as a known limitation, not silently hidden |

## 9. Implementation Plan (as executed)

1. Project foundation — FastAPI skeleton, Docker Compose, health checks
2. Database schema + migration runner
3. RAG ingestion pipeline (transcript loading, chunking, embedding, storage)
4. Agent/chat layer — retrieval, LLM provider abstraction with fallback,
   grounded chat endpoint, session management
5. Frontend + artifact viewer *(next)*
6. Ship 30 for 30 skill *(stretch, time-permitting)*
7. Tests, documentation polish, demo video
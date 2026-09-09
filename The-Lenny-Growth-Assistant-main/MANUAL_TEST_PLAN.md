# Manual Test Plan — The Lenny Growth Assistant

Automated tests (`backend/tests/`) cover unit-level logic (chunking,
threshold filtering) and API contracts (validation, structured errors).
The following require a running full stack (`docker compose up`) and are
best verified manually.

## 1. Full stack startup
- [ ] `cp .env.example .env && docker compose up --build` starts all 4
      services (postgres, ollama, backend, frontend) with one command
- [ ] `curl http://localhost:8000/health` returns 200 within ~30s of startup
- [ ] `curl http://localhost:8000/health/ready` shows `database: true` once
      Postgres is healthy

## 2. Ingestion
- [ ] `docker compose exec ollama ollama pull nomic-embed-text` succeeds
- [ ] `docker compose exec backend python -m app.rag.ingestion.ingest --limit 3`
      ingests 3 transcripts without error
- [ ] Re-running the same command immediately logs `skip ... (already applied)`
      for all 3 — confirms idempotent re-runs
- [ ] `SELECT count(*) FROM documents; SELECT count(*) FROM chunks;` shows
      non-zero rows matching the ingested count

## 3. Grounded chat (happy path)
- [ ] Open `http://localhost:5173`, ask a question closely related to an
      ingested episode's topic (e.g. "How can I speak more confidently in
      difficult conversations?" if the Matt Abrahams/Alisa Cohn episodes
      are ingested)
- [ ] Response shows `grounded: true`-equivalent UI state (solid border,
      not dashed)
- [ ] Source chips appear below the answer, matching real ingested episodes

## 4. Grounded chat (no-match path)
- [ ] Ask a question about a topic definitely not in the ingested subset
      (e.g. a very specific, obscure claim)
- [ ] Response is honest ("I don't have relevant information..."), not a
      fabricated answer with invented quotes/timestamps
- [ ] UI shows the dashed/ungrounded visual treatment

## 5. Session continuity
- [ ] Ask a follow-up question in the same session (don't click "New chat")
- [ ] Response demonstrates awareness of the prior turn (e.g. "as I
      mentioned..." or a coherent continuation)
- [ ] `GET /api/sessions/{id}/messages` returns both turns in order

## 6. Artifact generation + viewer
- [ ] Type an instruction (e.g. "Write a markdown summary of onboarding
      advice"), click "Generate Artifact"
- [ ] Right panel opens with rendered content (not raw markdown text, not
      raw HTML tags visible)
- [ ] Inspect the iframe element: confirm `sandbox="allow-scripts"` is
      present and `allow-same-origin` is NOT present

## 7. Ship 30 for 30 skill
- [ ] `POST /api/content/ship30` with a topic related to ingested content
- [ ] Response includes `grounded: true` and a non-empty `sources` list
- [ ] Essay has identifiable structure: a distinct opening, headed
      sections, and a closing takeaway (exact word count may vary — see
      PRD.md known limitations re: local model instruction-following)

## 8. Resilience
- [ ] Stop the ollama container (`docker compose stop ollama`) and send a
      chat message: expect a clean 503 with a readable error message in
      the UI, not a hang or crash
- [ ] `docker compose start ollama`, confirm chat works again without
      restarting the backend
- [ ] Stop postgres (`docker compose stop postgres`): confirm
      `/health` still returns 200 (liveness), `/health/ready` returns 503
- [ ] Restart postgres: confirm the backend reconnects without a manual
      backend restart (verify via `/health/ready`)

## 9. Provider toggle
- [ ] With `LLM_PROVIDER=anthropic` and no `ANTHROPIC_API_KEY` set, send a
      chat message: confirm it falls back to Ollama (check
      `llm_provider` field in the response — should read `"ollama"`) and
      a warning is logged, not a hard failure
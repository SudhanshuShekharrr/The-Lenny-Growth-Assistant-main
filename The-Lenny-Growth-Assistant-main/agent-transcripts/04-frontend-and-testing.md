# Session 4: Frontend, Artifact Viewer & Automated Tests

## Frontend stack decision

Built as static HTML/JS/CSS served via nginx rather than React+TypeScript,
given the compressed timeline. Confirmed this was acceptable by re-reading
the assignment's actual 4.3 requirement text ("frontend needs an Artifact
Viewer... rendering beside the chat") — it does not mandate a specific
framework. Documented as a deliberate scope choice in `design.md`, with
React+TS/Vite noted as a compatible future migration since the backend is
a stack-agnostic REST API.

---

## Bug: Artifact panel rendered blank despite a valid API response

**Symptom:** `POST /api/artifacts` returned 200 with real markdown
content (verified via `Invoke-RestMethod` directly against the API), but
the frontend's artifact panel showed nothing.

**Root cause:** Stale cached JavaScript in the browser — a prior edit
(source-citation deduplication) had been saved to the file, but the
browser was still running an older cached version of `index.html`.

**Fix:** Hard refresh (Ctrl+Shift+R) resolved it immediately. No code
defect — a caching/testing-process issue, not a logic bug. Documented
here because it cost real debugging time and is a useful lesson for
anyone extending the frontend: always hard-refresh after editing the
single-file frontend during manual testing.

---

## Security: Sandboxed artifact rendering

Per the assignment's explicit security requirement (4.3), generated
HTML/Markdown is rendered inside `<iframe sandbox="allow-scripts">` using
`srcdoc` — deliberately **omitting** `allow-same-origin`, so any script in
generated content cannot access the parent page's DOM, cookies, or make
authenticated requests back to the backend API. This isolation strategy
is documented in `architecture.md` §7 so an evaluator can see exactly
what's permitted (scripts execute, but in a null/opaque origin) and what's
blocked (same-origin access, top-level navigation).

---

## Bug caught by automated tests: `AttributeError` when `db_pool` was unset

**Symptom:** Two API contract tests failed with
`AttributeError: 'State' object has no attribute 'db_pool'` when hitting
`/api/chat` and `/api/sessions` in a test environment where the FastAPI
lifespan hook (which sets `app.state.db_pool`) hadn't run.

**Root cause:** `chat.py` and `sessions.py` accessed
`request.app.state.db_pool` directly, while `health.py` (written earlier,
during the resilience-focused Session 1 work) used the safer
`getattr(request.app.state, "db_pool", None)` pattern. The inconsistency
was only surfaced once real tests exercised the code path.

**Fix:** Standardized on `getattr(..., None)` across all three route
files. Directly demonstrates the value of the automated test suite: this
defensive-coding gap wasn't visible in normal manual testing (the lifespan
hook always runs in `docker compose up`), only in an isolated test
environment — exactly the kind of edge case tests are meant to catch.

---

## Test suite summary

14 automated tests added, all passing:
- 4 unit tests for the chunking algorithm (empty input, short input,
  overlap correctness, no data loss across chunk boundaries)
- 6 API contract tests (validation errors, structured error shapes,
  graceful failure when dependencies are unavailable)
- 2 retrieval threshold calibration tests
- 2 health/liveness tests (carried over from Session 1)

Manual test plan (`MANUAL_TEST_PLAN.md`) covers scenarios that require a
full running stack and can't be meaningfully unit-tested: end-to-end
ingestion idempotency, grounded vs. ungrounded chat behavior, artifact
sandbox verification, and resilience under dependency failure (stopping
Ollama/Postgres mid-session).
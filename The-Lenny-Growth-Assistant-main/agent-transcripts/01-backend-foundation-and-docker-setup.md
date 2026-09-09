# Session 1: Backend Foundation & Docker Setup

## Stack decision: Node.js → Python/FastAPI

**Initial request:** Build Step 1 in JavaScript/Node.js with Express.

**Problem caught before building further:** The assignment brief
explicitly mandates FastAPI as the backend framework. Building in Node.js
would have contradicted an explicit requirement, likely costing points on
"Technical execution."

**Fix:** Flagged the conflict directly, presented the trade-off (Node.js
already built vs. switching to match spec), developer chose to switch.
Rebuilt the backend foundation in Python/FastAPI with the same scope:
health/readiness endpoints, structured error handling, asyncpg connection
pooling, Docker Compose orchestration.

**Lesson applied going forward:** Always cross-check specific tech
requests against the actual assignment spec before building, not just the
developer's most recent phrasing.

---

## Bug: Server crashes if Postgres is unreachable at startup

**Symptom:** `uvicorn` process exited immediately when the database
connection failed during the FastAPI lifespan startup hook.

**Root cause:** `app.state.db_pool = await create_pool(settings)` was
called without exception handling — any connection failure propagated up
and killed the process.

**Fix:** Wrapped pool creation in try/except; on failure, logs the error,
sets `app.state.db_pool = None`, and starts the app anyway in a degraded
mode. `/health` still returns 200 (liveness); `/health/ready` correctly
reports 503 until the DB recovers. Verified by manually stopping Postgres
and confirming the backend no longer crash-loops.

---

## Bug: Structured 404s not returned for routing-level errors

**Symptom:** Custom JSON error handler worked for application-raised
errors, but a plain `/nonexistent` route returned FastAPI's default
`{"detail":"Not Found"}` instead of the app's structured error shape.

**Root cause:** The exception handler was registered against
`fastapi.exceptions.HTTPException`, but Starlette's routing layer raises
`starlette.exceptions.HTTPException` directly for unmatched routes —
different class, so the handler wasn't triggered.

**Fix:** Registered the handler against `starlette.exceptions.HTTPException`
(the base class) instead. Verified with a live curl test that `/nonexistent`
now returns the structured `{"error": {...}}` shape with a request ID.

---

## Infra: Docker Desktop disk space exhaustion (Windows/WSL2)

**Symptom:** `ollama pull llama3.1:8b` stalled indefinitely
(`1% ... 11m35s` and not progressing). Investigation revealed the
developer's C: drive had only 2GB free — Docker Desktop's WSL2 data
volume lives on C: by default.

**Attempted fix #1 (failed):** Used Docker Desktop's GUI "Disk image
location" setting to move data to D:. Failed with
`failed to move WSL disk: copying vm disk with robocopy: exit status 8`
— the GUI move needs scratch space on the *source* drive to do a
copy-then-delete, which wasn't available with only 2GB free.

**Fix that worked:** Manual WSL export/import directly to D:, bypassing
the GUI's copy-in-place approach:
wsl --shutdown
wsl --export docker-desktop-data D:\WSLBackup\docker-desktop-data.tar
wsl --unregister docker-desktop-data
wsl --import docker-desktop-data D:\DockerData D:\WSLBackup\docker-desktop-data.tar --version 2
Verified via `docker system df` showing real usage and Docker Desktop's
Resources panel showing the new D: path.

**Secondary fix:** Switched from `llama3.1:8b` (4.9GB) to `llama3.2:1b`
(1.3GB) as the local model to reduce both disk and pull-time pressure
given the remaining constraints.

---

## Bug: Ollama container reported unhealthy despite running correctly

**Symptom:** `docker compose up` failed with
`dependency failed to start: container ...-ollama-1 is unhealthy`, even
though `docker compose exec ollama ollama list` worked fine manually.

**Root cause:** The Docker Compose healthcheck used `curl`, but the
`ollama/ollama` base image doesn't include a `curl` binary —
`docker inspect ... .State.Health` showed `"/bin/sh: 1: curl: not found"`
on every healthcheck attempt.

**Fix:** Changed the healthcheck command to `ollama list || exit 1`,
using Ollama's own CLI instead of an external tool that wasn't present in
the image.

**Follow-up bug (self-inflicted during the fix):** While editing the
compose file, the same `ollama list` healthcheck line was accidentally
also pasted into the **postgres** service block (leaving two conflicting
`test:` keys under `ollama`, and an invalid one under `postgres`), which
then made postgres report unhealthy instead. Caught by inspecting the
full compose file after the first fix didn't resolve the issue, and
corrected by restoring `pg_isready` for the postgres healthcheck.
# Session 2: Database Schema & RAG Ingestion Pipeline

## Schema design

Verified the real transcript repo structure directly (cloned
`ChatPRD/lennys-podcast-transcripts` and inspected an actual episode file)
before designing the ingestion parser, rather than assuming the format —
confirmed `episodes/{guest-slug}/transcript.md` with YAML frontmatter
(guest, title, publish_date, etc.) followed by a markdown body.

Designed `sessions`, `messages`, `documents`, `chunks` tables with
`pgvector` for embeddings and a `content_hash` column on `documents` to
support idempotent re-ingestion.

---

## Bug: Migration script couldn't find the migrations folder in the container

**Symptom:** `Migrations dir not found: /db/migrations` when running the
migration runner inside the backend container.

**Root cause:** The Dockerfile only copies the `app/` directory into the
image — the `db/` folder (containing SQL migrations) was never included,
and the path calculation in `migrate.py` was also computed incorrectly
for the containerized environment.

**Fix:** Added a bind mount (`./db:/app/db:ro`) in `docker-compose.yml`
so the migrations directory is available at runtime without needing to
rebuild the image on every schema change, and corrected the path
resolution in the migration runner.

**Secondary bug:** Running `python app/debug_retrieval.py` directly
raised `ModuleNotFoundError: No module named 'app'` — running a script by
file path doesn't add the working directory to `sys.path` the way
`python -m app.debug_retrieval` does. Standardized on the `-m` invocation
for all internal scripts going forward.

---

## Performance issue: Full 303-episode ingestion was ~12 hours

**Symptom:** After ~10 episodes, timestamps showed ~140 seconds/episode —
extrapolated to the full 303-episode corpus, that's roughly 12 hours,
infeasible given the assignment deadline.

**Root cause:** Ollama defaults to `OLLAMA_NUM_PARALLEL=1` (processes one
request at a time), and the ingestion script also embeds chunks
sequentially — both bottlenecks compounding.

**Decision (documented as a scope trade-off in PRD.md, not silently
worked around):** Rather than engineering concurrency improvements under
time pressure, ingestion was run in the background across multiple
sessions, safely interruptible (each document is ingested inside a DB
transaction, so an interrupted run only loses the one in-progress
document) and resumable via the `content_hash` skip-if-unchanged check.
Eventually completed the full 303/303 episodes across background runs.

---

## Bug: Retrieval silently returned far fewer results than requested

**Symptom:** A debug query requesting `LIMIT 10` similar chunks only
returned 3 rows, even though the corpus had thousands of chunks.

**Root cause:** The `ivfflat` vector index was created with `lists = 100`
(sized for the eventual full 303-episode corpus), but at the time only a
partial corpus (~37 episodes, ~3,000 chunks) was ingested. `pgvector`
defaults to probing only 1 list per query — with that few chunks spread
across 100 lists, most of the dataset was never actually searched.

**Fix:** Added `SET LOCAL ivfflat.probes = 10` before retrieval queries
to widen the search at a small latency cost — appropriate for a
partial/growing corpus. Verified the same query afterward returned the
full requested row count with more informative distance variation.

---

## Bug: Relevance threshold miscalibrated (over-filtering)

**Symptom:** A genuinely relevant question ("How can I speak more
confidently in difficult conversations?") returned "I don't have relevant
information," even though a directly on-topic episode (Matt Abrahams,
"How to speak more confidently and persuasively") was in the corpus.

**Root cause:** An initial relevance-distance threshold (0.35) was set
without checking it against real corpus data — actual relevant matches in
this embedding space/corpus size were landing at ~0.37-0.40, just above
the arbitrary cutoff.

**Fix:** Built a small debug script (`debug_retrieval.py`) to print raw
cosine distances for a query against the live corpus, confirmed the real
distribution, and recalibrated the threshold based on evidence (0.42,
later tightened to 0.40 — see Session 3) rather than guessing.
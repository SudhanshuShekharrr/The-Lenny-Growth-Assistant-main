# Agent Transcripts

This folder documents the AI-assisted development process for The Lenny
Growth Assistant, built using Claude (Anthropic) as a coding agent through
a conversational chat interface, with the developer directing, reviewing,
and testing every change against a running Docker Compose stack.

## Why these files, not a raw chat export

Rather than a raw copy-paste of the full conversation (which mixes UI
mechanics, screenshots, and repeated back-and-forth), these files are
organized by work session and problem/fix pairs — the signal an evaluator
actually wants: what was attempted, what failed, why, and how it was
resolved. Every issue documented here is a real bug encountered and fixed
during this project, not a hypothetical.

## Sessions

1. **01-backend-foundation-and-docker-setup.md** — Initial stack decision
   (Node.js → Python/FastAPI switch), Docker Compose setup, and several
   real infrastructure failures (disk space, healthcheck misconfiguration,
   Windows/WSL disk relocation issues).
2. **02-database-schema-and-rag-ingestion.md** — Postgres/pgvector schema,
   migration runner, transcript ingestion pipeline, and the ivfflat
   retrieval bug that silently limited search results.
3. **03-agent-layer-and-grounding-fixes.md** — Chat/session endpoints, LLM
   provider abstraction, and — most importantly — two real hallucination
   incidents caught during manual testing and how they were fixed.
4. **04-frontend-and-testing.md** — Chat UI, sandboxed artifact viewer,
   automated test suite, and a defensive-coding gap the tests caught.

## No secrets

No API keys or credentials were ever pasted into the development
conversation. `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` remained blank
placeholders throughout (Ollama was used for all local testing). Nothing
in this folder required scrubbing.
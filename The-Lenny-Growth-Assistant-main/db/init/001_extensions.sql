-- Runs automatically on first container start (mounted into
-- /docker-entrypoint-initdb.d by docker-compose).
--
-- Step 1 only enables extensions; actual tables (sessions, messages,
-- documents, chunks) are defined in a later step once the RAG/session
-- schema is finalized in architecture.md.

-- pgvector will back the RAG retrieval step (transcript chunk embeddings).
-- Declared here now so the base image already has it available.
CREATE EXTENSION IF NOT EXISTS vector;

-- Used for UUID primary keys (sessions, messages, documents).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

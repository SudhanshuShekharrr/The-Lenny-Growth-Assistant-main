-- Initial schema: sessions, messages, documents, chunks (RAG-ready)
-- Run manually or via a migration runner (see backend/app/db/migrate.py below)

-- --- Sessions ---
-- One row per chat session. No user auth in scope yet — user_metadata is
-- a free-form JSONB field so we don't need a users table for Step 2.
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    llm_provider TEXT NOT NULL DEFAULT 'ollama',
    user_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- Messages ---
-- Every user/assistant turn in a session. `sources` stores which transcript
-- chunks grounded an assistant answer (for citation display in the UI).
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    llm_provider TEXT,
    llm_model TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- --- Documents ---
-- One row per ingested transcript (episode). Tracks source traceability
-- and lets us support refresh/re-ingestion later without duplicating data.
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path TEXT NOT NULL UNIQUE,   -- e.g. repo file path or URL
    title TEXT,
    episode_number TEXT,
    published_at DATE,
    content_hash TEXT NOT NULL,          -- detects changed source files on re-ingest
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- Chunks ---
-- Transcript text split into retrievable pieces, with embeddings for
-- vector similarity search. Dimension 768 assumed for a common local
-- embedding model (e.g. nomic-embed-text) — adjust if a different model
-- is chosen in the RAG ingestion step.
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

-- Vector similarity index (IVFFlat) — created after data exists ideally,
-- but safe to create empty; Postgres will just rebuild lists as needed.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

-- --- updated_at auto-touch trigger for sessions ---
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- Per-answer-key text chunks with 128-D embeddings (same width as answer_keys.embedding).

CREATE TABLE IF NOT EXISTS public.answer_key_chunks (
    chunk_id TEXT PRIMARY KEY,
    answer_key_id TEXT NOT NULL REFERENCES public.answer_keys (id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    embedding vector(128) NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_answer_key_chunks_key_index UNIQUE (answer_key_id, chunk_index)
);

COMMENT ON TABLE public.answer_key_chunks IS 'Chunked model-answer text + embeddings for granular retrieval';
COMMENT ON COLUMN public.answer_key_chunks.embedding IS '128-D; same backend as answer_keys (MiniLM projected or hash)';

CREATE INDEX IF NOT EXISTS idx_answer_key_chunks_key_id
    ON public.answer_key_chunks (answer_key_id, chunk_index ASC);

CREATE INDEX IF NOT EXISTS idx_answer_key_chunks_embedding_hnsw
    ON public.answer_key_chunks
    USING hnsw (embedding vector_cosine_ops);

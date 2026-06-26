-- Hybrid RAG: full-text search on sheet chunks (pairs with vector HNSW in init_db / GRADE API)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_text_fts
    ON public.rag_chunks
    USING gin (to_tsvector('english', text_content));

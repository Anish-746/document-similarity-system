CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL DEFAULT 'text',
    is_indexed BOOLEAN NOT NULL DEFAULT false,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS minhash_signatures (
    document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    signature INTEGER[] NOT NULL,
    num_shingles INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS similarity_pairs (
    id SERIAL PRIMARY KEY,
    document_a_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_b_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    estimated_similarity DOUBLE PRECISION NOT NULL,
    exact_similarity DOUBLE PRECISION NOT NULL,
    is_flagged BOOLEAN NOT NULL DEFAULT false,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pair UNIQUE (document_a_id, document_b_id)
);

CREATE INDEX IF NOT EXISTS ix_similarity_pairs_a ON similarity_pairs (document_a_id);
CREATE INDEX IF NOT EXISTS ix_similarity_pairs_b ON similarity_pairs (document_b_id);
CREATE INDEX IF NOT EXISTS ix_similarity_pairs_flagged ON similarity_pairs (is_flagged);

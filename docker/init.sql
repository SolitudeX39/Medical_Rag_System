CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    file_hash TEXT PRIMARY KEY,
    pdf_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parent_chunks (
    parent_id TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL REFERENCES documents(file_hash),
    page INTEGER,
    parent_texts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS child_chunks (
    child_id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL REFERENCES parent_chunks(parent_id),
    child_text TEXT NOT NULL,
    embeddings vector(3072)
);

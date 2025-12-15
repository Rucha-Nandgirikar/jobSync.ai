-- Migration: Add answer_snippets and answer_embeddings tables for RAG over golden answers
USE job_scout_ai;

-- Store curated / high-quality Q&A snippets (cover letters, long-form answers, etc.)
CREATE TABLE IF NOT EXISTS answer_snippets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    title VARCHAR(255),
    category VARCHAR(100),
    source_type ENUM('manual', 'generated', 'imported') DEFAULT 'manual',
    original_question TEXT,
    answer_text LONGTEXT NOT NULL,
    liked_score TINYINT, -- optional 1–10 rating for ranking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_category (category),
    FULLTEXT INDEX ft_answer_text (answer_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Embeddings / text chunks for semantic search over answer_snippets
CREATE TABLE IF NOT EXISTS answer_embeddings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    snippet_id INT NOT NULL,
    chunk_index INT,
    embedding_vector JSON,
    chunk_text LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snippet_id) REFERENCES answer_snippets(id) ON DELETE CASCADE,
    INDEX idx_snippet_id (snippet_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;








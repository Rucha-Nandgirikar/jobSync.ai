-- Migration: Create jobs_archived table for retention
-- Moves old, non-applied jobs out of the main jobs table to keep the DB/UI clean.

USE job_scout_ai;

CREATE TABLE IF NOT EXISTS jobs_archived (
    id INT PRIMARY KEY AUTO_INCREMENT,
    original_job_id INT NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    source_id INT,
    external_id VARCHAR(255),
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    department VARCHAR(255),
    description LONGTEXT,
    requirements LONGTEXT,
    salary_min DECIMAL(10, 2),
    salary_max DECIMAL(10, 2),
    job_type ENUM('full_time', 'part_time', 'contract', 'internship', 'unknown') DEFAULT 'unknown',
    url VARCHAR(1000) NOT NULL,
    posting_date DATETIME,
    is_active BOOLEAN DEFAULT FALSE,
    crawled_at TIMESTAMP NULL,
    last_updated TIMESTAMP NULL,
    created_via ENUM('crawler', 'extension') NOT NULL DEFAULT 'crawler',

    UNIQUE KEY uniq_original_job_id (original_job_id),
    INDEX idx_archived_at (archived_at),
    INDEX idx_company (company),
    INDEX idx_posting_date (posting_date),
    INDEX idx_source_external (source_id, external_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;







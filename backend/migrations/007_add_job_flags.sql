-- Migration: Add per-user job flags (skip/not_fit/not_us) without creating applications

USE job_scout_ai;

CREATE TABLE IF NOT EXISTS job_flags (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    job_id INT NOT NULL,
    flag ENUM('skipped', 'not_fit', 'not_us') NOT NULL DEFAULT 'skipped',
    reason VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_user_job (user_id, job_id),
    INDEX idx_user_flag (user_id, flag),
    INDEX idx_job_id (job_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;







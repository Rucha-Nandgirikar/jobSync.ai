-- Create database
CREATE DATABASE IF NOT EXISTS job_scout_ai;
USE job_scout_ai;

-- Job Sources/Companies
CREATE TABLE job_sources (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    url VARCHAR(500) NOT NULL,
    scraper_type ENUM('lever', 'greenhouse', 'workday', 'ashby', 'custom') NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    target_departments JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_enabled (enabled),
    INDEX idx_scraper_type (scraper_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crawler Configurations
CREATE TABLE crawler_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_id INT NOT NULL,
    selector_xpath VARCHAR(1000),
    pagination_selector VARCHAR(1000),
    title_selector VARCHAR(1000),
    location_selector VARCHAR(1000),
    description_selector VARCHAR(1000),
    apply_link_selector VARCHAR(1000),
    custom_config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE,
    INDEX idx_source_id (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Resumes
CREATE TABLE resumes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    role VARCHAR(100),
    file_path VARCHAR(500) NOT NULL,
    skills JSON,
    experience_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Resume Embeddings (for RAG)
CREATE TABLE resume_embeddings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    resume_id INT NOT NULL,
    chunk_index INT,
    embedding_vector JSON,
    chunk_text LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    INDEX idx_resume_id (resume_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Jobs
CREATE TABLE jobs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_id INT NOT NULL,
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
    is_active BOOLEAN DEFAULT TRUE,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_external (source_id, external_id),
    FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE,
    FULLTEXT INDEX ft_title_company (title, company),
    FULLTEXT INDEX ft_description (description),
    INDEX idx_source_id (source_id),
    INDEX idx_posting_date (posting_date),
    INDEX idx_is_active (is_active),
    INDEX idx_job_type (job_type),
    INDEX idx_department (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cover Letters (must be created before applications since applications references it)
CREATE TABLE cover_letters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    job_id INT NOT NULL,
    resume_id INT NOT NULL,
    user_id INT NOT NULL,
    content LONGTEXT NOT NULL,
    file_path VARCHAR(500),
    model_used VARCHAR(100),
    temperature FLOAT,
    tokens_used INT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE RESTRICT,
    INDEX idx_user_id (user_id),
    INDEX idx_job_id (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Applications
CREATE TABLE applications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    job_id INT NOT NULL,
    resume_id INT NOT NULL,
    user_id INT NOT NULL,
    status ENUM('draft', 'submitted', 'reviewed', 'rejected', 'interviewed', 'offered') DEFAULT 'draft',
    cover_letter_id INT,
    applied_at DATETIME,
    last_status_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE RESTRICT,
    FOREIGN KEY (cover_letter_id) REFERENCES cover_letters(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_job_id (job_id),
    INDEX idx_applied_at (applied_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Application Answers (for Q&A)
CREATE TABLE application_answers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT NOT NULL,
    question TEXT NOT NULL,
    answer LONGTEXT NOT NULL,
    model_used VARCHAR(100),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    INDEX idx_application_id (application_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crawler Runs (for logging)
CREATE TABLE crawler_runs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_id INT NOT NULL,
    status ENUM('started', 'completed', 'failed') DEFAULT 'started',
    jobs_found INT DEFAULT 0,
    jobs_new INT DEFAULT 0,
    jobs_updated INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    INDEX idx_source_id (source_id),
    INDEX idx_started_at (started_at),
    FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Users (for multi-user support later)
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default job sources
INSERT INTO job_sources (name, url, scraper_type) VALUES
('Lever Jobs', 'https://jobs.lever.co', 'lever'),
('Greenhouse Jobs', 'https://boards.greenhouse.io', 'greenhouse'),
('Workday', 'https://www.workday.com', 'workday'),
('AshbyHQ', 'https://jobs.ashbyhq.com', 'ashby')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

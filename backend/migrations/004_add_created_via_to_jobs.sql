-- Migration: Add created_via column to jobs
-- Tracks whether a job was first created by crawler or extension

USE job_scout_ai;

ALTER TABLE jobs
ADD COLUMN created_via ENUM('crawler', 'extension') NOT NULL
    DEFAULT 'crawler'
    COMMENT 'How this job was first created (crawler vs extension)';

-- Optional: index if you plan to filter/group by this often
CREATE INDEX idx_jobs_created_via ON jobs(created_via);





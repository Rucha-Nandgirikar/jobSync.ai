-- Migration: Add user_suggestions column to application_answers
-- This allows users to provide hints/guidance for answer generation

USE job_scout_ai;

ALTER TABLE application_answers 
ADD COLUMN user_suggestions TEXT NULL COMMENT 'User-provided hints/guidance for answer generation';

-- Add index for faster queries when filtering by suggestions
CREATE INDEX idx_user_suggestions ON application_answers(user_suggestions(100));





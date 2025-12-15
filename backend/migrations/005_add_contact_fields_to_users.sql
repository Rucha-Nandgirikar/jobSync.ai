-- Migration: Add contact fields to users for cover letter headers

USE job_scout_ai;

ALTER TABLE users
ADD COLUMN phone VARCHAR(50) NULL AFTER email,
ADD COLUMN linkedin_url VARCHAR(255) NULL AFTER phone,
ADD COLUMN portfolio_url VARCHAR(255) NULL AFTER linkedin_url;





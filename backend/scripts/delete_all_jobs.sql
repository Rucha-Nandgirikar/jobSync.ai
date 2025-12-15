-- Delete all job records and related data
-- WARNING: This will delete ALL jobs, applications, and cover letters

-- Delete applications first (foreign key constraint)
DELETE FROM applications;

-- Delete cover letters (foreign key constraint)
DELETE FROM cover_letters;

-- Delete all jobs
DELETE FROM jobs;

-- Show count after deletion
SELECT COUNT(*) as remaining_jobs FROM jobs;

















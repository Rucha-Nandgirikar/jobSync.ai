-- Check job sources configuration
SELECT 
    id,
    name,
    url,
    scraper_type,
    enabled
FROM job_sources
WHERE scraper_type = 'ashby';

-- Check sample jobs being stored
SELECT 
    id,
    title,
    company,
    external_id,
    url,
    source_id
FROM jobs
ORDER BY id DESC
LIMIT 10;
















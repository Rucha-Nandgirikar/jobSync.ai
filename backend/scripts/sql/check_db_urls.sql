-- Check for jobs with wrong URLs (containing /jobs/)
SELECT 
    id, 
    title, 
    company, 
    external_id,
    url,
    CASE 
        WHEN url LIKE '%/jobs/%' THEN 'BAD - has /jobs/'
        WHEN url LIKE '%//%' THEN 'BAD - has double slash'
        ELSE 'GOOD'
    END as url_status
FROM jobs
ORDER BY id DESC
LIMIT 20;

-- Count by URL status
SELECT 
    CASE 
        WHEN url LIKE '%/jobs/%' THEN 'Contains /jobs/'
        WHEN url LIKE '%//%' THEN 'Has double slash'
        ELSE 'Good'
    END as status,
    COUNT(*) as count
FROM jobs
GROUP BY status;
















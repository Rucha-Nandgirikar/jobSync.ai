"""Crawler services"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def crawl_all_sources(max_post_age_hours: Optional[int] = None) -> Dict[str, Any]:
    """Crawl all enabled job sources"""
    from app.database import execute_query
    
    query = "SELECT id FROM job_sources WHERE enabled = TRUE"
    sources = execute_query(query)
    
    results = []
    for source in sources:
        result = await crawl_source(source["id"], max_post_age_hours=max_post_age_hours)
        results.append(result)
    
    return {"sources_crawled": len(results), "results": results}

def _parse_iso_datetime_maybe(value: Any):
    """Best-effort parse of ISO-ish datetime strings.

    Supports common forms like '2025-12-01T10:11:12Z' by converting Z → +00:00.
    Returns a timezone-aware datetime or None if unparsable.
    """
    try:
        from datetime import datetime, timezone

        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if not isinstance(value, str):
            return None
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def crawl_source(source_id: int, max_post_age_hours: Optional[int] = None) -> Dict[str, Any]:
    """Crawl a specific job source"""
    from app.database import execute_query, execute_insert, execute_update
    from datetime import datetime, timedelta, timezone
    import httpx
    
    try:
        # Log crawl start
        run_insert = """
        INSERT INTO crawler_runs (source_id, status, started_at)
        VALUES (:source_id, 'started', NOW())
        """
        run_id = execute_insert(run_insert, {"source_id": source_id})
        
        query = "SELECT scraper_type, url, name, target_departments FROM job_sources WHERE id = :id"
        source = execute_query(query, {"id": source_id})
        
        if not source:
            return {"status": "failed", "message": "Source not found"}
        
        scraper_type = source[0]['scraper_type']
        company_name = source[0].get('name', 'Unknown')
        target_departments = source[0].get('target_departments')
        if target_departments and isinstance(target_departments, str):
            import json
            target_departments = json.loads(target_departments)
        
        # Import appropriate crawler
        if scraper_type == 'lever':
            from .lever import crawl_lever
            jobs = await crawl_lever(source[0]['url'])
        elif scraper_type == 'greenhouse':
            from .greenhouse import crawl_greenhouse
            jobs = await crawl_greenhouse(source[0]['url'])
        elif scraper_type == 'workday':
            from .workday import crawl_workday
            jobs = await crawl_workday(source[0]['url'])
        elif scraper_type == 'ashby':
            from .ashby import crawl_ashby
            jobs = await crawl_ashby(source[0]['url'])
        else:
            return {"status": "failed", "message": f"Unknown scraper type: {scraper_type}"}
        
        # Store jobs in database
        new_count = 0
        updated_count = 0
        crawled_job_urls = set()
        
        # Optional: only store very recent jobs when posting_date is available.
        # Note: Many scrapers currently return posting_date=None, in which case
        # we keep the job (we cannot safely filter by age).
        if max_post_age_hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=int(max_post_age_hours))
            filtered_by_age = []
            for job in jobs:
                dt = _parse_iso_datetime_maybe(job.get("posting_date"))
                if dt is None or dt >= cutoff:
                    filtered_by_age.append(job)
            jobs = filtered_by_age

        # Filter jobs by department if target_departments specified
        # Filtering happens on title/description - no need to extract department in crawlers
        if target_departments:
            import re
            # Create flexible patterns that match "engineering", "software engineering", etc.
            dept_patterns = []
            for dept in target_departments:
                # Allow for variations like "Engineering", "Software Engineering", "SWE", etc.
                dept_normalized = dept.lower().replace(' ', r'\s+')
                dept_patterns.append(re.compile(r'\b' + dept_normalized + r'\b', re.I))
                # Also match common variations
                if 'engineering' in dept.lower():
                    dept_patterns.append(re.compile(r'\b(software|backend|frontend|full.?stack|devops|infrastructure|sre)\s+engineer', re.I))
            
            filtered_jobs = []
            for job in jobs:
                title = job.get('title', '').lower()
                description = job.get('description', '').lower()
                
                # Check if job matches any target department in title or description
                matches = False
                for pattern in dept_patterns:
                    if pattern.search(title) or pattern.search(description):
                        matches = True
                        break
                
                if matches:
                    # Set department for storage after filtering
                    job['department'] = target_departments[0]  # Use first target as primary
                    filtered_jobs.append(job)
            
            jobs = filtered_jobs
            logger.info(f"Filtered to {len(jobs)} jobs matching departments: {target_departments}")
        
        for job in jobs:
            try:
                # Use company name from job_sources, not from scraper
                job['company'] = company_name
                
                # Check if job already exists BEFORE insert
                check_query = """
                SELECT id FROM jobs 
                WHERE source_id = :source_id 
                    AND (external_id = :external_id OR url = :url)
                LIMIT 1
                """
                existing = execute_query(
                    check_query, 
                    {
                        "source_id": source_id, 
                        "external_id": job.get('external_id') or '',
                        "url": job.get('url')
                    }
                )
                
                # Try to insert or update
                insert_query = """
                INSERT INTO jobs 
                (source_id, external_id, title, company, location, department,
                 description, job_type, url, posting_date, is_active, crawled_at)
                VALUES 
                (:source_id, :external_id, :title, :company, :location, :department,
                 :description, :job_type, :url, :posting_date, TRUE, NOW())
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    url = VALUES(url),
                    description = VALUES(description),
                    department = VALUES(department),
                    location = VALUES(location),
                    job_type = VALUES(job_type),
                    posting_date = VALUES(posting_date),
                    last_updated = NOW(),
                    is_active = TRUE,
                    crawled_at = NOW()
                """
                
                execute_insert(insert_query, {
                    "source_id": source_id,
                    "external_id": job.get('external_id'),
                    "title": job.get('title'),
                    "company": company_name,
                    "location": job.get('location'),
                    "department": job.get('department'),  # Will be set by filter if target_departments specified
                    "description": job.get('description'),
                    "job_type": job.get('job_type', 'unknown'),
                    "url": job.get('url'),
                    "posting_date": job.get('posting_date')
                })
                
                crawled_job_urls.add(job.get('url'))
                
                if existing:
                    updated_count += 1
                else:
                    new_count += 1
                    
            except Exception as e:
                logger.error(f"Error storing job: {e}")
       
        # Mark jobs from this source that were NOT seen in this crawl as inactive.
        # This ensures closed/expired roles stop showing up in the active job list,
        # while keeping history for existing applications.
        try:
            # Fetch all currently active jobs for this source
            active_jobs_query = """
            SELECT id, url
            FROM jobs
            WHERE source_id = :source_id AND is_active = TRUE
            """
            active_jobs = execute_query(active_jobs_query, {"source_id": source_id})

            deactivate_query = """
            UPDATE jobs
            SET is_active = FALSE,
                last_updated = NOW()
            WHERE id = :job_id
            """

            for row in active_jobs:
                if row.get("url") not in crawled_job_urls:
                    execute_update(deactivate_query, {"job_id": row["id"]})
        except Exception as e:
            logger.error(f"Error marking inactive jobs for source {source_id}: {e}")

        # Update crawler run status
        update_run = """
        UPDATE crawler_runs
        SET status = 'completed', 
            jobs_found = :found,
            jobs_new = :new,
            jobs_updated = :updated,
            completed_at = NOW()
        WHERE id = :run_id
        """
        execute_update(update_run, {
            "run_id": run_id,
            "found": len(jobs),
            "new": new_count,
            "updated": updated_count
        })
        
        return {
            "status": "success",
            "source_id": source_id,
            "jobs_found": len(jobs),
            "jobs_new": new_count,
            "jobs_updated": updated_count
        }
    
    except Exception as e:
        logger.error(f"Crawl source {source_id} error: {e}")
        return {"status": "failed", "error": str(e)}

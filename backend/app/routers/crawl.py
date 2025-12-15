from fastapi import APIRouter, HTTPException, Query
import logging
from typing import Optional, List

from pydantic import BaseModel

from app.services.crawler import crawl_all_sources, crawl_source

router = APIRouter()
logger = logging.getLogger(__name__)


class JobSourceCreate(BaseModel):
    name: str
    url: str
    scraper_type: str  # ashby, greenhouse, lever, workday, custom
    enabled: bool = True
    target_departments: Optional[List[str]] = None


@router.get("/sources")
async def list_sources():
    """List configured job sources."""
    try:
        from app.database import execute_query

        rows = execute_query(
            """
            SELECT id, name, url, scraper_type, enabled, target_departments, created_at, updated_at
            FROM job_sources
            ORDER BY enabled DESC, id ASC
            """
        )
        return {"status": "success", "data": rows}
    except Exception as e:
        logger.error(f"List sources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources")
async def add_source(payload: JobSourceCreate):
    """Add (or update) a job source.

    NOTE: Crawlers require company-specific URLs, e.g.
    - Ashby: https://jobs.ashbyhq.com/<companySlug>
    - Greenhouse: https://boards.greenhouse.io/<company>
    - Lever: https://jobs.lever.co/<company>
    """
    try:
        from app.database import execute_insert, execute_query
        import json

        stype = (payload.scraper_type or "").strip().lower()
        if stype not in {"ashby", "greenhouse", "lever", "workday", "custom"}:
            raise HTTPException(status_code=400, detail="Invalid scraper_type")

        insert_sql = """
        INSERT INTO job_sources (name, url, scraper_type, enabled, target_departments)
        VALUES (:name, :url, :stype, :enabled, :target_departments)
        ON DUPLICATE KEY UPDATE
            url = VALUES(url),
            scraper_type = VALUES(scraper_type),
            enabled = VALUES(enabled),
            target_departments = VALUES(target_departments),
            updated_at = CURRENT_TIMESTAMP
        """
        execute_insert(
            insert_sql,
            {
                "name": payload.name[:255],
                "url": payload.url[:500],
                "stype": stype,
                "enabled": bool(payload.enabled),
                "target_departments": json.dumps(payload.target_departments) if payload.target_departments else None,
            },
        )

        row = execute_query(
            "SELECT id FROM job_sources WHERE name = :name LIMIT 1",
            {"name": payload.name[:255]},
        )
        return {"status": "success", "data": {"source_id": row[0]["id"] if row else None}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _window_to_hours(window: Optional[str]) -> Optional[int]:
    if not window:
        return None
    w = window.strip().lower()
    mapping = {
        "24h": 24,
        "1d": 24,
        "7d": 7 * 24,
        "15d": 15 * 24,
        "30d": 30 * 24,
        "1m": 30 * 24,
        "1mo": 30 * 24,
        "month": 30 * 24,
    }
    return mapping.get(w)


@router.post("/trigger")
async def trigger_crawl(
    source_id: Optional[int] = Query(None),
    max_post_age_hours: Optional[int] = Query(
        None,
        ge=1,
        le=24 * 90,
        description="If set, only store jobs whose posting_date is within the last N hours (when posting_date is available).",
    ),
    max_post_age_days: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="If set, only store jobs whose posting_date is within the last N days (when posting_date is available).",
    ),
    age_window: Optional[str] = Query(
        None,
        description="Convenience windows for crawl-time filtering: 24h, 7d, 15d, 30d (aka 1m).",
    ),
):
    """
    Manually trigger a crawl
    - If source_id provided: crawl specific source
    - If no source_id: crawl all enabled sources
    """
    try:
        # Resolve a single effective hours window (hours > days > preset window)
        effective_hours: Optional[int] = None
        if max_post_age_hours is not None:
            effective_hours = int(max_post_age_hours)
        elif max_post_age_days is not None:
            effective_hours = int(max_post_age_days) * 24
        else:
            effective_hours = _window_to_hours(age_window)

        if source_id:
            result = await crawl_source(source_id, max_post_age_hours=effective_hours)
            return {
                "status": "success",
                "message": f"Crawled source {source_id}",
                "data": result
            }
        else:
            result = await crawl_all_sources(max_post_age_hours=effective_hours)
            return {
                "status": "success",
                "message": "Crawled all sources",
                "data": result
            }
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_crawl_status():
    """Get status of recent crawls"""
    try:
        from app.database import execute_query
        
        query = """
        SELECT 
            id, source_id, status, jobs_found, jobs_new, 
            started_at, completed_at
        FROM crawler_runs
        ORDER BY started_at DESC
        LIMIT 20
        """
        
        results = execute_query(query)
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_crawl_stats():
    """Get crawling statistics"""
    try:
        from app.database import execute_query
        
        query = """
        SELECT 
            COUNT(*) as total_jobs,
            COUNT(DISTINCT source_id) as sources,
            MAX(crawled_at) as last_crawl
        FROM jobs
        """
        
        result = execute_query(query)
        return {
            "status": "success",
            "data": result[0] if result else {}
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



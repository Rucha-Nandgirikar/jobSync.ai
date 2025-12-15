"""Chrome-related backend APIs (Rapid Apply extension).

All Rapid Apply–specific FastAPI routes live in this package.

The capture-job endpoint persists jobs into the main `jobs` table so they can be
used immediately for cover-letter generation and Q&A.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.database import execute_insert, execute_query, execute_update

router = APIRouter()
logger = logging.getLogger(__name__)


def _canonicalize_job_url(job_url: str) -> str:
    """Canonicalize job URLs so 'overview' and 'application' routes map to one job.

    For Ashby, the same job can be:
      /<company>/<uuid>
      /<company>/<uuid>/application
    We store only the overview URL (strip trailing '/application') and drop query/fragment.
    """
    try:
        parsed = urlparse(str(job_url))
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        path = parsed.path or ""
        if path.endswith("/application"):
            path = path[: -len("/application")]
        while path.endswith("/") and path != "/":
            path = path[:-1]
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return str(job_url)


class CaptureJobRequest(BaseModel):
    """Payload sent by the Rapid Apply extension when capturing a job page."""

    user_id: int
    job_url: HttpUrl
    company_name: Optional[str] = None
    company_url: Optional[HttpUrl] = None
    job_title: Optional[str] = None
    job_description: str
    source: Optional[str] = "ashby"  # ashby, greenhouse, lever, workday, other


def _normalize_source(scraper: Optional[str]) -> str:
    """Map arbitrary source strings to a valid job_sources.scraper_type value."""
    if not scraper:
        return "custom"
    s = scraper.lower()
    if s in {"ashby", "greenhouse", "lever", "workday"}:
        return s
    return "custom"


def _get_or_create_job_source(
    scraper_type: str, company_name: Optional[str], job_url: str
) -> int:
    """Return a job_sources.id for the given source.

    We try to identify a source by (scraper_type, base_url). If not found, we
    create one and enable it.
    """
    parsed = urlparse(str(job_url))
    host = parsed.netloc or "unknown-host"
    base_url = f"{parsed.scheme or 'https'}://{host}" if host else str(job_url)
    name = (company_name or host or "Custom Source")[:255]

    rows = execute_query(
        "SELECT id FROM job_sources WHERE scraper_type = :stype AND url = :url LIMIT 1",
        {"stype": scraper_type, "url": base_url[:500]},
    )
    if rows:
        return int(rows[0]["id"])

    # Name is unique in schema; handle collisions by updating the existing row.
    insert_sql = """
    INSERT INTO job_sources (name, url, scraper_type, enabled)
    VALUES (:name, :url, :stype, TRUE)
    ON DUPLICATE KEY UPDATE
        url = VALUES(url),
        scraper_type = VALUES(scraper_type),
        enabled = TRUE,
        updated_at = CURRENT_TIMESTAMP
    """
    source_id = execute_insert(
        insert_sql,
        {"name": name, "url": base_url[:500], "stype": scraper_type},
    )
    if not source_id:
        # If ON DUPLICATE KEY UPDATE fired, re-select id by name.
        rows = execute_query(
            "SELECT id FROM job_sources WHERE name = :name LIMIT 1",
            {"name": name},
        )
        if rows:
            return int(rows[0]["id"])
        raise RuntimeError("Failed to resolve job_source id after upsert")
    return int(source_id)


@router.post("/capture-job")
async def capture_job(request: CaptureJobRequest):
    """Capture a job posting from the Rapid Apply extension."""
    try:
        job_url = _canonicalize_job_url(str(request.job_url))

        # 1) Existing job by URL
        existing = execute_query(
            "SELECT id, created_via FROM jobs WHERE url = :url LIMIT 1",
            {"url": job_url},
        )
        if existing:
            job_id = existing[0]["id"]
            execute_update(
                """
                UPDATE jobs
                SET title = COALESCE(:title, title),
                    company = COALESCE(:company, company),
                    description = :description,
                    is_active = TRUE,
                    crawled_at = NOW(),
                    last_updated = NOW()
                WHERE id = :job_id
                """,
                {
                    "title": request.job_title,
                    "company": request.company_name,
                    "description": request.job_description,
                    "job_id": job_id,
                },
            )
            job_rows = execute_query(
                "SELECT id, title, company, url, created_via FROM jobs WHERE id = :id LIMIT 1",
                {"id": job_id},
            )
            return {
                "status": "success",
                "data": {
                    "job_id": job_id,
                    "created_via": existing[0].get("created_via", "crawler"),
                    "job": job_rows[0] if job_rows else {"id": job_id, "url": job_url},
                },
            }

        # 2) Create new job
        scraper_type = _normalize_source(request.source)
        source_id = _get_or_create_job_source(
            scraper_type=scraper_type,
            company_name=request.company_name,
            job_url=job_url,
        )

        insert_sql = """
        INSERT INTO jobs (
            source_id, title, company, description, url, job_type,
            is_active, created_via, crawled_at
        )
        VALUES (
            :source_id, :title, :company, :description, :url, :job_type,
            TRUE, 'extension', NOW()
        )
        """
        title = (request.job_title or "Unknown Role")[:255]
        company = (request.company_name or "Unknown Company")[:255]
        job_id = execute_insert(
            insert_sql,
            {
                "source_id": source_id,
                "title": title,
                "company": company,
                "description": request.job_description,
                "url": job_url[:1000],
                "job_type": "unknown",
            },
        )

        job_rows = execute_query(
            "SELECT id, title, company, url, created_via FROM jobs WHERE id = :id LIMIT 1",
            {"id": job_id},
        )
        return {
            "status": "success",
            "data": {
                "job_id": job_id,
                "created_via": "extension",
                "job": job_rows[0] if job_rows else {"id": job_id, "title": title, "company": company, "url": job_url},
            },
        }
    except Exception as e:
        logger.error("Rapid Apply capture_job error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))



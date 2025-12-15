import logging

from app.config import settings
from app.database import execute_query, execute_update

logger = logging.getLogger(__name__)


def archive_old_jobs(retention_days: int | None = None) -> dict:
    """Move old, non-applied jobs out of `jobs` into `jobs_archived`.

    Rules:
    - Only archive jobs that have NO applications and NO cover letters.
    - Age is based on COALESCE(posting_date, crawled_at).
    - After inserting into jobs_archived, delete from jobs.
    """
    days = int(retention_days or settings.JOB_RETENTION_DAYS)

    # Insert eligible jobs into archive table
    insert_sql = """
    INSERT INTO jobs_archived (
        original_job_id,
        archived_at,
        source_id, external_id, title, company, location, department,
        description, requirements, salary_min, salary_max, job_type,
        url, posting_date, is_active, crawled_at, last_updated, created_via
    )
    SELECT
        j.id AS original_job_id,
        NOW() AS archived_at,
        j.source_id, j.external_id, j.title, j.company, j.location, j.department,
        j.description, j.requirements, j.salary_min, j.salary_max, j.job_type,
        j.url, j.posting_date, j.is_active, j.crawled_at, j.last_updated, j.created_via
    FROM jobs j
    WHERE
        COALESCE(j.posting_date, j.crawled_at) < DATE_SUB(NOW(), INTERVAL :days DAY)
        AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id)
        AND NOT EXISTS (SELECT 1 FROM cover_letters c WHERE c.job_id = j.id)
        AND NOT EXISTS (SELECT 1 FROM jobs_archived ja WHERE ja.original_job_id = j.id)
    """

    # Delete from jobs after archiving (same eligibility conditions)
    delete_sql = """
    DELETE j
    FROM jobs j
    WHERE
        COALESCE(j.posting_date, j.crawled_at) < DATE_SUB(NOW(), INTERVAL :days DAY)
        AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id)
        AND NOT EXISTS (SELECT 1 FROM cover_letters c WHERE c.job_id = j.id)
    """

    try:
        # Count eligible first (for reporting)
        count_sql = """
        SELECT COUNT(*) AS cnt
        FROM jobs j
        WHERE
            COALESCE(j.posting_date, j.crawled_at) < DATE_SUB(NOW(), INTERVAL :days DAY)
            AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id)
            AND NOT EXISTS (SELECT 1 FROM cover_letters c WHERE c.job_id = j.id)
        """
        rows = execute_query(count_sql, {"days": days})
        eligible = int(rows[0]["cnt"]) if rows else 0

        # Archive then purge
        execute_update(insert_sql, {"days": days})
        deleted = execute_update(delete_sql, {"days": days})

        logger.info(
            "Archived old jobs: eligible=%s retention_days=%s deleted_from_jobs=%s",
            eligible,
            days,
            deleted,
        )
        return {"eligible": eligible, "archived": eligible, "deleted": deleted, "retention_days": days}
    except Exception:
        logger.exception("Failed to archive old jobs")
        raise



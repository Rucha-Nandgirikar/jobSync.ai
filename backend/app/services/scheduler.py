import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = None

def init_scheduler() -> AsyncIOScheduler:
    """Initialize and configure APScheduler"""
    global scheduler
    
    scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
    
    # Add daily crawl job at 6 AM
    scheduler.add_job(
        crawl_daily_job,
        CronTrigger(
            hour=settings.CRAWL_SCHEDULE_HOUR,
            minute=settings.CRAWL_SCHEDULE_MINUTE
        ),
        id='daily_crawl',
        name='Daily Job Board Crawl',
        replace_existing=True
    )

    # Add daily retention job (archive + purge) shortly after crawl
    scheduler.add_job(
        archive_daily_job,
        CronTrigger(
            hour=settings.ARCHIVE_SCHEDULE_HOUR,
            minute=settings.ARCHIVE_SCHEDULE_MINUTE,
        ),
        id="daily_archive",
        name="Daily Job Retention (Archive/Purge)",
        replace_existing=True,
    )

    # Add daily export job (XLSX snapshot)
    scheduler.add_job(
        export_daily_job,
        CronTrigger(
            hour=settings.EXPORT_SCHEDULE_HOUR,
            minute=settings.EXPORT_SCHEDULE_MINUTE,
        ),
        id="daily_export",
        name="Daily Applications Export (XLSX)",
        replace_existing=True,
    )
    
    logger.info(f"Scheduler initialized. Daily crawl at {settings.CRAWL_SCHEDULE_HOUR}:{settings.CRAWL_SCHEDULE_MINUTE:02d}")
    return scheduler

async def crawl_daily_job():
    """Daily crawl job that runs at scheduled time"""
    try:
        logger.info("Starting scheduled daily crawl")
        
        from app.services.crawler import crawl_all_sources
        
        result = await crawl_all_sources()
        
        logger.info(f"Daily crawl completed: {result}")
        
    except Exception as e:
        logger.error(f"Daily crawl failed: {e}")


async def archive_daily_job():
    """Daily retention job that archives/purges old, non-applied jobs."""
    try:
        from app.services.retention import archive_old_jobs

        logger.info("Starting scheduled archive/purge (retention_days=%s)", settings.JOB_RETENTION_DAYS)
        result = archive_old_jobs(settings.JOB_RETENTION_DAYS)
        logger.info("Archive/purge completed: %s", result)
    except Exception as e:
        logger.error("Archive/purge failed: %s", e)


async def export_daily_job():
    """Daily export job: write an XLSX export for each user with applications."""
    try:
        from app.database import execute_query
        from app.services.exporter import write_daily_applications_export

        user_rows = execute_query(
            "SELECT DISTINCT user_id FROM applications ORDER BY user_id ASC"
        )
        user_ids = [int(r["user_id"]) for r in (user_rows or []) if r.get("user_id") is not None]
        if not user_ids:
            # MVP default user
            user_ids = [1]

        for uid in user_ids:
            try:
                write_daily_applications_export(uid)
            except Exception:
                logger.exception("Daily export failed for user_id=%s", uid)

        logger.info("Daily export completed for users=%s", user_ids)
    except Exception as e:
        logger.error("Daily export job failed: %s", e)

def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance"""
    return scheduler



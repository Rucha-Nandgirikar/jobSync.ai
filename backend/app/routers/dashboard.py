from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging
from typing import Optional
from io import BytesIO
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)


class ApplicationStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class ApplicationCreate(BaseModel):
    user_id: int
    job_id: int
    resume_id: int
    status: str = "draft"


class JobFlagUpsert(BaseModel):
    user_id: int
    flag: str = "skipped"  # skipped | not_fit | not_us
    reason: Optional[str] = None

@router.get("/jobs")
async def get_jobs(
    user_id: int = Query(default=1, description="User ID, defaults to 1 for MVP"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500, description="Jobs per page (max 500)"),
    status: Optional[str] = None,
    is_active: Optional[str] = Query(None),
    department: Optional[str] = Query(None, description="Filter by department (e.g., 'engineering')"),
    tag: Optional[str] = Query("all", description="Job tag filter: all, applied, remaining, skipped"),
    fresh_hours: Optional[int] = Query(
        None,
        ge=1,
        le=24 * 30,
        description="If set, only return jobs crawled in the last N hours (uses jobs.crawled_at).",
    ),
):
    """Get jobs with pagination and filters"""
    try:
        from app.database import execute_query
        
        offset = (page - 1) * limit
        
        # Build WHERE clause
        where_clauses = []
        params = {"user_id": user_id, "limit": limit, "offset": offset, "tag": tag}
        
        # Parse is_active as boolean from string query param
        if is_active is not None:
            is_active_bool = is_active.lower() in ("true", "1", "yes")
            where_clauses.append("j.is_active = :is_active")
            params["is_active"] = is_active_bool
        
        # Filter by department (case-insensitive)
        if department:
            where_clauses.append("LOWER(j.department) LIKE LOWER(:department)")
            params["department"] = f"%{department}%"
        
        # Freshness filter: only show jobs crawled in the last N hours
        if fresh_hours is not None:
            where_clauses.append("j.crawled_at >= DATE_SUB(NOW(), INTERVAL :fresh_hours HOUR)")
            params["fresh_hours"] = int(fresh_hours)

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Tag-based HAVING clause for applied/remaining filters
        having_clause = """
        HAVING
            (:tag = 'all')
            OR (:tag = 'applied' AND COUNT(a.id) > 0)
            OR (:tag = 'skipped' AND MAX(jf.flag) IS NOT NULL)
            OR (:tag = 'remaining' AND COUNT(a.id) = 0 AND MAX(jf.flag) IS NULL)
        """
        
        # Main jobs query with tag filter
        query = f"""
        SELECT 
            j.id, j.title, j.company, j.location, j.department,
            j.description, j.url, j.job_type,
            j.salary_min, j.salary_max, j.posting_date, j.crawled_at,
            COUNT(a.id) as application_count,
            MAX(jf.flag) AS user_flag,
            MAX(jf.reason) AS user_flag_reason
        FROM jobs j
        LEFT JOIN applications a ON j.id = a.job_id AND a.user_id = :user_id
        LEFT JOIN job_flags jf ON j.id = jf.job_id AND jf.user_id = :user_id
        WHERE {where_clause}
        GROUP BY j.id
        {having_clause}
        ORDER BY j.posting_date DESC, j.crawled_at DESC
        LIMIT :limit OFFSET :offset
        """
        
        results = execute_query(query, params)
        
        # Total count using same grouping + having
        count_query = f"""
        SELECT COUNT(*) as total FROM (
            SELECT j.id
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id AND a.user_id = :user_id
            LEFT JOIN job_flags jf ON j.id = jf.job_id AND jf.user_id = :user_id
            WHERE {where_clause}
            GROUP BY j.id
            {having_clause}
        ) sub
        """
        count_result = execute_query(count_query, {k: v for k, v in params.items() if k not in ['limit', 'offset']})
        total = count_result[0]['total'] if count_result else 0
        
        return {
            "status": "success",
            "data": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "offset": offset,
                "total": total,
                "total_pages": (total + limit - 1) // limit
            }
        }
    except Exception as e:
        logger.error(f"Get jobs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/flag")
async def flag_job(job_id: int, payload: JobFlagUpsert):
    """Flag a job as skipped / not_fit / not_us for this user (does not create an application)."""
    try:
        from app.database import execute_insert

        flag = (payload.flag or "skipped").strip().lower()
        if flag not in ("skipped", "not_fit", "not_us"):
            raise HTTPException(status_code=400, detail="Invalid flag")

        sql = """
        INSERT INTO job_flags (user_id, job_id, flag, reason, created_at, updated_at)
        VALUES (:user_id, :job_id, :flag, :reason, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            flag = VALUES(flag),
            reason = VALUES(reason),
            updated_at = CURRENT_TIMESTAMP
        """
        execute_insert(
            sql,
            {
                "user_id": payload.user_id,
                "job_id": job_id,
                "flag": flag,
                "reason": (payload.reason or None),
            },
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Flag job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}/flag")
async def unflag_job(job_id: int, user_id: int):
    """Remove a user's flag from a job."""
    try:
        from app.database import execute_update

        rows = execute_update(
            "DELETE FROM job_flags WHERE user_id = :user_id AND job_id = :job_id",
            {"user_id": user_id, "job_id": job_id},
        )
        return {"status": "success", "data": {"deleted": rows}}
    except Exception as e:
        logger.error(f"Unflag job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/applications")
async def get_applications(
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """Get user applications with pagination and filters"""
    try:
        from app.database import execute_query
        
        offset = (page - 1) * limit
        
        where_clause = "WHERE a.user_id = :user_id"
        params = {"user_id": user_id, "limit": limit, "offset": offset}
        
        if status:
            where_clause += " AND a.status = :status"
            params["status"] = status
        
        query = f"""
        SELECT 
            a.id, a.status, a.applied_at,
            j.id as job_id, j.title, j.company, j.location,
            j.job_type, j.url,
            r.id as resume_id, r.filename as resume_name
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN resumes r ON a.resume_id = r.id
        {where_clause}
        ORDER BY a.applied_at DESC
        LIMIT :limit OFFSET :offset
        """
        
        results = execute_query(query, params)
        
        return {
            "status": "success",
            "data": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        logger.error(f"Get applications error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications/export")
async def export_applications(
    user_id: int,
    format: str = Query("xlsx", description="xlsx or csv"),
):
    """Export applications (joined with jobs + resumes) to an Excel/CSV download."""
    try:
        from fastapi.responses import StreamingResponse, Response
        from app.database import execute_query

        rows = execute_query(
            """
            SELECT
                a.id AS application_id,
                a.status,
                a.applied_at,
                a.created_at AS application_created_at,
                j.id AS job_id,
                j.title,
                j.company,
                j.location,
                j.department,
                j.url,
                j.posting_date,
                j.crawled_at,
                r.id AS resume_id,
                r.filename AS resume_filename,
                r.role AS resume_role
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN resumes r ON a.resume_id = r.id
            WHERE a.user_id = :user_id
            ORDER BY COALESCE(a.applied_at, a.created_at) DESC
            """,
            {"user_id": user_id},
        )

        fmt = (format or "xlsx").lower()
        filename = f"applications_user_{user_id}.{fmt}"

        if fmt == "csv":
            import csv

            output = BytesIO()
            # Write UTF-8 CSV (Excel compatible)
            text = output
            fieldnames = list(rows[0].keys()) if rows else [
                "application_id","status","applied_at","application_created_at","job_id","title","company",
                "location","department","url","posting_date","crawled_at","resume_id","resume_filename","resume_role"
            ]
            sio = []
            # Build CSV in-memory as bytes
            import io as _io
            s = _io.StringIO()
            w = csv.DictWriter(s, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({k: ("" if v is None else v) for k, v in r.items()})
            data_bytes = s.getvalue().encode("utf-8")
            return Response(
                content=data_bytes,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        # Default: XLSX
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Applications"

        headers = list(rows[0].keys()) if rows else [
            "application_id","status","applied_at","application_created_at","job_id","title","company",
            "location","department","url","posting_date","crawled_at","resume_id","resume_filename","resume_role"
        ]
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h) for h in headers])

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        return StreamingResponse(
            bio,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Export applications error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications/export/latest")
async def download_latest_export(user_id: int):
    """Download the most recent daily XLSX export for this user.

    If no export exists yet, we generate one on-demand.
    """
    try:
        from fastapi.responses import FileResponse
        from app.services.exporter import find_latest_export_path, write_daily_applications_export

        path = find_latest_export_path(user_id)
        if not path:
            path = write_daily_applications_export(user_id)

        filename = Path(path).name
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    except Exception as e:
        logger.error(f"Download latest export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/applications")
async def create_application(payload: ApplicationCreate):
    """Create a new application row (used by extension + UI)."""
    try:
        from app.database import execute_insert, execute_query, execute_update

        # Prevent duplicate applications for the same (user_id, job_id) in MVP.
        existing = execute_query(
            "SELECT id, status, applied_at FROM applications WHERE user_id = :user_id AND job_id = :job_id LIMIT 1",
            {"user_id": payload.user_id, "job_id": payload.job_id},
        )
        if existing:
            # If caller is trying to mark as submitted, upgrade status and stamp applied_at once.
            if payload.status and payload.status != existing[0].get("status"):
                execute_update(
                    """
                    UPDATE applications
                    SET
                        status = :status,
                        resume_id = :resume_id,
                        last_status_update = NOW(),
                        applied_at = CASE
                            WHEN :status = 'submitted' AND applied_at IS NULL THEN NOW()
                            ELSE applied_at
                        END,
                        updated_at = NOW()
                    WHERE id = :app_id
                    """,
                    {
                        "app_id": existing[0]["id"],
                        "status": payload.status,
                        "resume_id": payload.resume_id,
                    },
                )
            return {
                "status": "success",
                "data": {"application_id": existing[0]["id"], "deduped": True},
            }

        insert_query = """
        INSERT INTO applications (job_id, resume_id, user_id, status, applied_at, created_at, updated_at)
        VALUES (
            :job_id,
            :resume_id,
            :user_id,
            :status,
            CASE WHEN :status = 'submitted' THEN NOW() ELSE NULL END,
            NOW(),
            NOW()
        )
        """
        app_id = execute_insert(
            insert_query,
            {
                "job_id": payload.job_id,
                "resume_id": payload.resume_id,
                "user_id": payload.user_id,
                "status": payload.status,
            },
        )

        return {
            "status": "success",
            "data": {"application_id": app_id},
        }
    except Exception as e:
        logger.error(f"Create application error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/applications/{application_id}")
async def update_application_status(
    application_id: int,
    update: ApplicationStatusUpdate
):
    """Update application status.

    If the new status is 'submitted', we also stamp applied_at (once).
    This enables daily counts of submitted applications.
    """
    try:
        from app.database import execute_update
        
        query = """
        UPDATE applications
        SET 
            status = :status,
            last_status_update = NOW(),
            applied_at = CASE
                WHEN :status = 'submitted' AND applied_at IS NULL THEN NOW()
                ELSE applied_at
            END
        WHERE id = :app_id
        """
        
        rows = execute_update(query, {
            "app_id": application_id,
            "status": update.status
        })
        
        if rows == 0:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return {
            "status": "success",
            "message": "Application updated"
        }
    except Exception as e:
        logger.error(f"Update application error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_dashboard_stats(user_id: int):
    """Get dashboard statistics"""
    try:
        from app.database import execute_query
        
        query = """
        SELECT 
            COUNT(*) as total_applications,
            SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) as submitted,
            SUM(CASE WHEN status = 'reviewed' THEN 1 ELSE 0 END) as reviewed,
            SUM(CASE WHEN status = 'interviewed' THEN 1 ELSE 0 END) as interviewed,
            SUM(CASE WHEN status = 'offered' THEN 1 ELSE 0 END) as offered,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(
                CASE 
                    WHEN status = 'submitted' 
                         AND DATE(applied_at) = CURRENT_DATE 
                    THEN 1 ELSE 0 
                END
            ) as today_submitted,
            (
                SELECT COUNT(*)
                FROM jobs
                WHERE DATE(crawled_at) = CURRENT_DATE
            ) as today_jobs,
            (
                SELECT COUNT(DISTINCT LOWER(TRIM(company)))
                FROM jobs
                WHERE DATE(crawled_at) = CURRENT_DATE
                  AND company IS NOT NULL
                  AND TRIM(company) <> ''
            ) as today_unique_companies,
            (
                SELECT COUNT(DISTINCT LOWER(TRIM(company)))
                FROM jobs
                WHERE company IS NOT NULL
                  AND TRIM(company) <> ''
            ) as total_unique_companies
        FROM applications
        WHERE user_id = :user_id
        """
        
        result = execute_query(query, {"user_id": user_id})
        
        return {
            "status": "success",
            "data": result[0] if result else {}
        }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}")
async def get_job_details(job_id: int, user_id: int):
    """Get detailed job information"""
    try:
        from app.database import execute_query
        
        query = """
        SELECT *
        FROM jobs
        WHERE id = :job_id
        """
        
        result = execute_query(query, {"job_id": job_id})
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "status": "success",
            "data": result[0]
        }
    except Exception as e:
        logger.error(f"Get job details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


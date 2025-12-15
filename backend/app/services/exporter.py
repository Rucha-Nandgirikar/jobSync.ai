import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.database import execute_query

logger = logging.getLogger(__name__)


def _fetch_application_export_rows(user_id: int) -> List[Dict[str, Any]]:
    return execute_query(
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


def build_applications_xlsx_bytes(user_id: int) -> bytes:
    """Build an XLSX export for a user's applications and return bytes."""
    from openpyxl import Workbook

    rows = _fetch_application_export_rows(user_id)
    headers = list(rows[0].keys()) if rows else [
        "application_id",
        "status",
        "applied_at",
        "application_created_at",
        "job_id",
        "title",
        "company",
        "location",
        "department",
        "url",
        "posting_date",
        "crawled_at",
        "resume_id",
        "resume_filename",
        "resume_role",
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def write_daily_applications_export(user_id: int, exports_dir: Optional[str] = None) -> str:
    """Write an XLSX export to disk and return the absolute path."""
    out_dir = Path(exports_dir or settings.EXPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d")
    path = out_dir / f"applications_user_{user_id}_{stamp}.xlsx"

    data = build_applications_xlsx_bytes(user_id)
    path.write_bytes(data)
    logger.info("Wrote applications export for user_id=%s to %s", user_id, path)
    return str(path)


def find_latest_export_path(user_id: int, exports_dir: Optional[str] = None) -> Optional[str]:
    out_dir = Path(exports_dir or settings.EXPORTS_DIR)
    if not out_dir.exists():
        return None
    pattern = f"applications_user_{user_id}_*.xlsx"
    candidates = list(out_dir.glob(pattern))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(latest)







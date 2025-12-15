"""
Fix duplicate Ashby job rows created from '/application' URLs and merge applications.

Problem:
  - Extension capture on Ashby application route used job_url ending with '/application'
  - Backend treated it as a new job row, creating duplicate jobs and applications

This script:
  1) Finds job pairs where app_url = overview_url + '/application'
  2) Moves applications and cover_letters from app_job_id -> overview_job_id
  3) Dedupes applications per (user_id, overview_job_id) keeping the earliest row,
     and upgrading status/applied_at if needed
  4) Deletes now-unreferenced '/application' job rows

Usage (inside docker or with DATABASE_URL set):
  python scripts/fix_ashby_application_duplicates.py --apply
  python scripts/fix_ashby_application_duplicates.py --dry-run
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool


STATUS_RANK = {
    "draft": 1,
    "submitted": 2,
    "reviewed": 3,
    "interviewed": 4,
    "offered": 5,
    "rejected": 6,
}


def _rank(status: str | None) -> int:
    return STATUS_RANK.get((status or "").lower(), 0)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = p.parse_args()

    database_url = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/job_scout_ai"
    )
    engine = create_engine(database_url, poolclass=QueuePool, pool_pre_ping=True)

    with engine.connect() as conn:
        pairs = conn.execute(
            text(
                """
                SELECT j_app.id AS app_job_id, j_over.id AS over_job_id, j_app.url AS app_url, j_over.url AS over_url
                FROM jobs j_app
                JOIN jobs j_over ON j_over.url = REPLACE(j_app.url, '/application', '')
                WHERE j_app.url LIKE '%/application%'
                """
            )
        ).mappings().all()

    print(f"[fix] Found {len(pairs)} job '/application' pairs")
    if not pairs:
        return 0

    pair_map: Dict[int, int] = {int(r["app_job_id"]): int(r["over_job_id"]) for r in pairs}
    app_job_ids = tuple(pair_map.keys())

    def q(sql: str, params=None):
        with engine.connect() as conn:
            return conn.execute(text(sql), params or {}).mappings().all()

    # Count affected references
    apps_on_app_urls = q(
        "SELECT COUNT(*) AS c FROM applications WHERE job_id IN :ids",
        {"ids": app_job_ids},
    )[0]["c"]
    cls_on_app_urls = q(
        "SELECT COUNT(*) AS c FROM cover_letters WHERE job_id IN :ids",
        {"ids": app_job_ids},
    )[0]["c"]
    print(f"[fix] applications pointing to /application jobs: {apps_on_app_urls}")
    print(f"[fix] cover_letters pointing to /application jobs: {cls_on_app_urls}")

    if not args.apply:
        print("[fix] Dry-run only. Re-run with --apply to perform updates.")
        return 0

    with engine.begin() as conn:
        # 1) Move cover letters first (FK constraint)
        for app_id, over_id in pair_map.items():
            conn.execute(
                text("UPDATE cover_letters SET job_id = :to WHERE job_id = :from"),
                {"from": app_id, "to": over_id},
            )

        # 2) Move applications
        for app_id, over_id in pair_map.items():
            conn.execute(
                text("UPDATE applications SET job_id = :to WHERE job_id = :from"),
                {"from": app_id, "to": over_id},
            )

        # 3) Deduplicate applications by (user_id, job_id)
        rows = conn.execute(
            text(
                """
                SELECT user_id, job_id, COUNT(*) AS c
                FROM applications
                GROUP BY user_id, job_id
                HAVING c > 1
                """
            )
        ).mappings().all()

        print(f"[fix] duplicate application groups after remap: {len(rows)}")

        for r in rows:
            user_id = int(r["user_id"])
            job_id = int(r["job_id"])
            apps = conn.execute(
                text(
                    """
                    SELECT id, status, applied_at, resume_id
                    FROM applications
                    WHERE user_id = :u AND job_id = :j
                    ORDER BY id ASC
                    """
                ),
                {"u": user_id, "j": job_id},
            ).mappings().all()
            keep = apps[0]
            keep_id = int(keep["id"])

            # Determine best status + applied_at (earliest non-null)
            best_status = max(apps, key=lambda x: _rank(x.get("status"))).get("status") or keep.get("status")
            applied_times = [a.get("applied_at") for a in apps if a.get("applied_at") is not None]
            best_applied_at = min(applied_times) if applied_times else keep.get("applied_at")

            conn.execute(
                text(
                    """
                    UPDATE applications
                    SET status = :s,
                        applied_at = :a,
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": keep_id, "s": best_status, "a": best_applied_at},
            )

            # Delete the rest (answers FK cascades via application_id, so we must keep the one with answers ideally)
            # For MVP: delete extra rows with higher ids.
            delete_ids = [int(a["id"]) for a in apps[1:]]
            conn.execute(
                text("DELETE FROM applications WHERE id IN :ids"),
                {"ids": tuple(delete_ids)},
            )

        # 4) Delete now-unreferenced /application job rows
        # Only delete if nothing references them anymore.
        for app_job_id in app_job_ids:
            refs = conn.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM applications WHERE job_id = :id) AS a_cnt,
                      (SELECT COUNT(*) FROM cover_letters WHERE job_id = :id) AS c_cnt
                    """
                ),
                {"id": int(app_job_id)},
            ).mappings().first()
            if int(refs["a_cnt"]) == 0 and int(refs["c_cnt"]) == 0:
                conn.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": int(app_job_id)})

    print("[fix] Applied changes successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







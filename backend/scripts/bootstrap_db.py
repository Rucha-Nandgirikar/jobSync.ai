import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool


ATS_PATTERNS = {
    "lever": re.compile(r"lever\.co", re.I),
    "greenhouse": re.compile(r"greenhouse\.io", re.I),
    "ashby": re.compile(r"ashbyhq\.com", re.I),
    "workday": re.compile(r"workday|myworkdayjobs", re.I),
}


def _detect_scraper_type(url: str, fallback: str = "custom") -> str:
    if not url:
        return fallback
    for name, pattern in ATS_PATTERNS.items():
        if pattern.search(url):
            return name
    return fallback


def _wait_for_db(engine, timeout_seconds: int) -> None:
    start = time.time()
    last_err: Optional[Exception] = None
    while time.time() - start < timeout_seconds:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:  # pragma: no cover
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"DB not reachable within {timeout_seconds}s: {last_err}")


def _load_json(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return [d for d in data if isinstance(d, dict)]


def _seed_job_sources(engine, json_paths: List[Path]) -> Dict[str, Any]:
    inserted_or_updated = 0
    skipped = 0

    upsert_sql = text(
        """
        INSERT INTO job_sources (name, url, scraper_type, enabled, target_departments)
        VALUES (:name, :url, :scraper_type, :enabled, :target_departments)
        ON DUPLICATE KEY UPDATE
            url = VALUES(url),
            scraper_type = VALUES(scraper_type),
            enabled = VALUES(enabled),
            target_departments = VALUES(target_departments),
            updated_at = CURRENT_TIMESTAMP
        """
    )

    with engine.begin() as conn:
        for jp in json_paths:
            companies = _load_json(jp)
            for c in companies:
                name = (c.get("name") or "").strip()
                if not name:
                    continue

                careers_url = (c.get("careers_url") or c.get("url") or "").strip()
                if not careers_url:
                    skipped += 1
                    continue

                scraper_type = (c.get("scraper_type") or "").strip().lower()
                if not scraper_type:
                    scraper_type = _detect_scraper_type(careers_url, fallback="custom")
                if scraper_type not in {"lever", "greenhouse", "ashby", "workday", "custom"}:
                    scraper_type = _detect_scraper_type(careers_url, fallback="custom")

                enabled = bool(c.get("enabled", True))
                target_departments = c.get("target_departments") or ["Engineering", "Software Engineering"]
                if not isinstance(target_departments, list):
                    target_departments = ["Engineering", "Software Engineering"]

                conn.execute(
                    upsert_sql,
                    {
                        "name": name[:255],
                        "url": careers_url[:500],
                        "scraper_type": scraper_type,
                        "enabled": enabled,
                        "target_departments": json.dumps(target_departments),
                    },
                )
                inserted_or_updated += 1

    return {"upserted": inserted_or_updated, "skipped_no_url": skipped, "files": [str(p) for p in json_paths]}


def _discover_seed_files(data_dir: Path) -> List[Path]:
    # Prefer explicit files if present; otherwise also include known startup lists.
    candidates = []
    explicit = data_dir / "ashby_startups.json"
    if explicit.exists():
        candidates.append(explicit)

    # Common legacy files
    for name in [
        "startups_sf.json",
        "startups_ny.json",
        "startups_remote.json",
        "startups_boston.json",
        "startups_mixed.json",
    ]:
        p = data_dir / name
        if p.exists():
            candidates.append(p)

    # De-dupe while preserving order
    seen = set()
    out: List[Path] = []
    for p in candidates:
        if str(p) in seen:
            continue
        seen.add(str(p))
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a fresh Job Scout AI database with seed data.")
    parser.add_argument("--data-dir", default="./data", help="Directory containing seed JSON files (default: ./data)")
    parser.add_argument("--timeout", type=int, default=120, help="DB connection timeout seconds (default: 120)")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/job_scout_ai")
    engine = create_engine(database_url, poolclass=QueuePool, pool_pre_ping=True)

    print(f"[bootstrap] DATABASE_URL={database_url}")
    _wait_for_db(engine, args.timeout)
    print("[bootstrap] DB reachable")

    data_dir = Path(args.data_dir).resolve()
    seed_files = _discover_seed_files(data_dir)
    if not seed_files:
        print(f"[bootstrap] No seed JSON files found under {data_dir}; skipping job_sources seed")
        return 0

    result = _seed_job_sources(engine, seed_files)
    print(f"[bootstrap] job_sources upserted={result['upserted']} skipped_no_url={result['skipped_no_url']}")
    print(f"[bootstrap] files={result['files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool


def _log(msg: str) -> None:
    print(msg, flush=True)


def _connect_engine(database_url: str):
    return create_engine(database_url, poolclass=QueuePool, pool_pre_ping=True)


def _wait_for_db(engine, timeout_s: int = 60) -> None:
    start = time.time()
    last_err: Optional[Exception] = None
    while time.time() - start < timeout_s:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return
        except Exception as e:  # pragma: no cover
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"DB did not become ready within {timeout_s}s: {last_err}")


def _table_exists(engine, table: str) -> bool:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = :t
                """
            ),
            {"t": table},
        ).mappings().all()
        return bool(rows and int(rows[0]["cnt"]) > 0)


def _detect_scraper_type(url: str, fallback: str = "custom") -> str:
    u = (url or "").lower()
    if "ashbyhq.com" in u:
        return "ashby"
    if "lever.co" in u:
        return "lever"
    if "greenhouse.io" in u:
        return "greenhouse"
    if "workday" in u or "myworkdayjobs" in u:
        return "workday"
    return fallback


def _seed_default_user(engine) -> None:
    # MVP expects user_id=1 in multiple places; seed a demo user if users is empty.
    password = "password"
    pwd_hash: str
    try:
        # Prefer bcrypt when available (matches backend dependency), but fall back
        # to pbkdf2_sha256 if bcrypt backend is not usable in the environment.
        from passlib.hash import bcrypt  # type: ignore

        pwd_hash = bcrypt.hash(password)
    except Exception:  # pragma: no cover - environment dependent
        from passlib.hash import pbkdf2_sha256  # type: ignore

        pwd_hash = pbkdf2_sha256.hash(password)

    with engine.begin() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) AS c FROM users")).mappings().first()["c"]
        if int(cnt) > 0:
            _log("👤 users table already has rows; skipping default user seed.")
            return

        conn.execute(
            text(
                """
                INSERT INTO users (username, email, password_hash, full_name, created_at, updated_at)
                VALUES (:u, :e, :p, :n, NOW(), NOW())
                """
            ),
            {
                "u": "Rucha Nandgirikar",
                "e": "rucha.nandgirikar.cs@gmail.com",
                "p": pwd_hash,
                "n": "Rucha Nandgirikar",
            },
        )
        _log("👤 Seeded default user: username=Rucha Nandgirikar email=rucha.nandgirikar.cs@gmail.com (password=password)")


def _disable_generic_sources(engine) -> None:
    generic_urls = [
        "https://jobs.lever.co",
        "https://boards.greenhouse.io",
        "https://www.workday.com",
        "https://jobs.ashbyhq.com",
    ]
    generic_names = ["Lever Jobs", "Greenhouse Jobs", "Workday", "AshbyHQ"]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE job_sources
                SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE url IN :urls OR name IN :names
                """
            ),
            {"urls": tuple(generic_urls), "names": tuple(generic_names)},
        )
    _log("🧹 Disabled generic placeholder job_sources (base URLs).")


def _upsert_job_source(
    engine,
    name: str,
    url: str,
    scraper_type: str,
    enabled: bool,
    target_departments: Optional[List[str]] = None,
) -> None:
    td_json = json.dumps(target_departments) if target_departments else None
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO job_sources (name, url, scraper_type, enabled, target_departments)
                VALUES (:name, :url, :stype, :enabled, :td)
                ON DUPLICATE KEY UPDATE
                    url = VALUES(url),
                    scraper_type = VALUES(scraper_type),
                    enabled = VALUES(enabled),
                    target_departments = VALUES(target_departments),
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "name": name[:255],
                "url": url[:500],
                "stype": scraper_type,
                "enabled": bool(enabled),
                "td": td_json,
            },
        )


def _import_sources_from_json(engine, json_path: Path) -> Dict[str, int]:
    companies = json.loads(json_path.read_text(encoding="utf-8"))
    imported = 0
    skipped = 0
    allowed = {"ashby", "greenhouse", "lever", "workday", "custom"}
    for c in companies:
        name = (c.get("name") or "").strip()
        url = (c.get("careers_url") or "").strip()
        if not name or not url:
            skipped += 1
            continue
        scraper_type = (c.get("scraper_type") or "").strip().lower() or _detect_scraper_type(url, fallback="custom")
        if scraper_type not in allowed:
            scraper_type = _detect_scraper_type(url, fallback="custom")
        if scraper_type not in allowed:
            scraper_type = "custom"
        enabled = bool(c.get("enabled", True))
        target_departments = c.get("target_departments") or ["Engineering", "Software Engineering"]
        if not isinstance(target_departments, list):
            target_departments = ["Engineering", "Software Engineering"]

        _upsert_job_source(
            engine,
            name=name,
            url=url,
            scraper_type=scraper_type,
            enabled=enabled,
            target_departments=target_departments,
        )
        imported += 1
    return {"imported": imported, "skipped": skipped}


def _discover_seed_files(data_dir: Path) -> List[Path]:
    # Prefer unified list first if present
    preferred = [
        data_dir / "ashby_startups.json",
        data_dir / "startups_sf.json",
        data_dir / "startups_ny.json",
        data_dir / "startups_remote.json",
        data_dir / "startups_boston.json",
        data_dir / "startups_mixed.json",
    ]
    files: List[Path] = [p for p in preferred if p.exists()]
    # Include any extra startups JSON files not in the preferred list
    for p in sorted(data_dir.glob("*.json")):
        if p.name.startswith("startups_") and p not in files and p.exists():
            files.append(p)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap seed data for Job Scout AI DB.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--data-dir", default=str(Path("data").resolve()))
    parser.add_argument("--skip-default-user", action="store_true")
    parser.add_argument("--disable-generic-sources", action="store_true", default=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    if not args.database_url:
        _log("❌ DATABASE_URL is not set.")
        return 2

    engine = _connect_engine(args.database_url)
    _log("⏳ Waiting for DB...")
    _wait_for_db(engine, timeout_s=int(args.timeout))
    _log("✅ DB reachable.")

    for required in ["job_sources", "users"]:
        if not _table_exists(engine, required):
            _log(f"❌ Missing table '{required}'. Run migrations first.")
            return 3

    if not args.skip_default_user:
        _seed_default_user(engine)

    if args.disable_generic_sources:
        _disable_generic_sources(engine)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        _log(f"⚠️ data dir not found: {data_dir}")
        return 0

    seed_files = _discover_seed_files(data_dir)
    if not seed_files:
        _log(f"⚠️ No seed JSON files found in {data_dir}")
        return 0

    totals = {"imported": 0, "skipped": 0}
    for f in seed_files:
        res = _import_sources_from_json(engine, f)
        totals["imported"] += res["imported"]
        totals["skipped"] += res["skipped"]
        _log(f"📥 Imported job_sources from {f.name}: {res}")

    with engine.connect() as conn:
        enabled_cnt = conn.execute(
            text("SELECT COUNT(*) AS c FROM job_sources WHERE enabled = TRUE")
        ).mappings().first()["c"]
        total_cnt = conn.execute(text("SELECT COUNT(*) AS c FROM job_sources")).mappings().first()["c"]
    _log(f"✅ job_sources: {int(total_cnt)} total, {int(enabled_cnt)} enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



import json
import sys
from pathlib import Path
import re

# Add parent directory to path to import database utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# Create database connection directly (bypass app.config)
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost:3306/job_scout_ai')
engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_pre_ping=True)

def execute_query(query: str, params: dict = None):
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]

def execute_insert(query: str, params: dict = None):
    from sqlalchemy import text
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result.lastrowid

def execute_update(query: str, params: dict = None):
    from sqlalchemy import text
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result.rowcount

# ATS detection patterns
ATS_PATTERNS = {
    "lever": re.compile(r"lever\.co", re.I),
    "greenhouse": re.compile(r"greenhouse\.io", re.I),
    "ashby": re.compile(r"ashbyhq\.com", re.I),
    "workday": re.compile(r"workday|myworkdayjobs", re.I),
}

def detect_scraper_type(url: str) -> str:
    """Auto-detect scraper type from careers URL"""
    if not url:
        return "unknown"
    for name, pattern in ATS_PATTERNS.items():
        if pattern.search(url):
            return name
    return "unknown"

def import_json_file(json_path: Path, location_type: str = None):
    """Import companies from a JSON file into job_sources table"""
    with open(json_path, 'r', encoding='utf-8') as f:
        companies = json.load(f)
    
    imported = 0
    skipped = 0
    
    for company in companies:
        name = company.get('name', '').strip()
        if not name:
            continue
        
        careers_url = company.get('careers_url', '').strip()
        location_type_json = company.get('location_type', location_type or 'unknown')
        scraper_type = detect_scraper_type(careers_url)
        enabled = company.get('enabled', True)
        
        # Get target_departments if specified (default to Engineering/Software Engineering)
        target_departments = company.get('target_departments', ["Engineering", "Software Engineering"])
        if not isinstance(target_departments, list):
            target_departments = ["Engineering", "Software Engineering"]
        
        # If no careers_url, skip (can't crawl)
        if not careers_url:
            skipped += 1
            continue
        
        # Check if already exists
        check_query = "SELECT id FROM job_sources WHERE name = :name"
        existing = execute_query(check_query, {"name": name})
        
        # Convert target_departments to JSON string for MySQL
        target_departments_json = json.dumps(target_departments)
        
        if existing:
            # Update existing
            update_query = """
            UPDATE job_sources 
            SET url = :url, scraper_type = :scraper_type, enabled = :enabled,
                target_departments = :target_departments
            WHERE name = :name
            """
            execute_update(
                update_query,
                {
                    "name": name,
                    "url": careers_url,
                    "scraper_type": scraper_type,
                    "enabled": enabled,
                    "target_departments": target_departments_json
                }
            )
            imported += 1
        else:
            # Insert new
            insert_query = """
            INSERT INTO job_sources (name, url, scraper_type, enabled, target_departments)
            VALUES (:name, :url, :scraper_type, :enabled, :target_departments)
            """
            execute_insert(
                insert_query,
                {
                    "name": name,
                    "url": careers_url,
                    "scraper_type": scraper_type,
                    "enabled": enabled,
                    "target_departments": target_departments_json
                }
            )
            imported += 1
    
    return imported, skipped

def main():
    json_files = [
        ('data/startups_sf.json', 'sf'),
        ('data/startups_ny.json', 'ny'),
        ('data/startups_remote.json', 'remote'),
        ('data/startups_boston.json', 'boston'),
        ('data/startups_mixed.json', 'mixed'),
        # Unified Ashby list (often used as a combined seed list)
        ('data/ashby_startups.json', 'mixed'),
    ]
    
    total_imported = 0
    total_skipped = 0
    
    for json_file, location_type in json_files:
        path = Path(json_file)
        if not path.exists():
            print(f"⚠️  {json_file} not found, skipping...")
            continue
        
        print(f"\n📂 Processing {json_file}...")
        imported, skipped = import_json_file(path, location_type)
        total_imported += imported
        total_skipped += skipped
        print(f"   ✓ Imported: {imported}, Skipped (no URL): {skipped}")
    
    print(f"\n✅ Total: {total_imported} companies imported, {total_skipped} skipped")
    
    # Show summary by scraper type
    summary_query = """
    SELECT scraper_type, COUNT(*) as count, SUM(enabled) as enabled_count
    FROM job_sources
    GROUP BY scraper_type
    """
    summary = execute_query(summary_query)
    print("\n📊 Summary by Scraper Type:")
    for row in summary:
        print(f"   {row['scraper_type']}: {row['count']} total, {row['enabled_count']} enabled")

if __name__ == "__main__":
    main()


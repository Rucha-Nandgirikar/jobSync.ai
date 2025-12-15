#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive Debug - Crawl ONE company and see everything
"""

import sys
import os
import asyncio
import logging

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

from app.services.crawler.ashby import crawl_ashby
from app.database import execute_query, execute_insert

async def debug_crawl_and_store(company_name: str, url: str, source_id: int):
    """Crawl ONE company and store, showing everything"""
    
    print(f"\n{'='*80}")
    print(f"🎯 INTERACTIVE DEBUG: {company_name}")
    print(f"{'='*80}\n")
    
    print(f"📍 URL: {url}")
    print(f"📍 Source ID: {source_id}\n")
    
    # Step 1: Crawl
    print("STEP 1: CRAWLING...")
    print("-"*80)
    jobs = await crawl_ashby(url)
    
    print(f"\n✅ Crawled {len(jobs)} jobs\n")
    
    # Step 2: Show what we got
    print("STEP 2: CRAWL RESULTS")
    print("-"*80)
    
    for i, job in enumerate(jobs[:5], 1):
        print(f"\n{i}. {job['title']}")
        print(f"   External ID: {job['external_id']}")
        print(f"   URL: {job['url']}")
        print(f"   Department: {job.get('department', 'N/A')}")
        print(f"   Location: {job['location']}")
        
        # Check URL
        if '//jobs/' in job['url']:
            print(f"   ❌❌❌ ERROR: Double slash //jobs/")
        elif '/jobs/' in job['url']:
            print(f"   ℹ️  Contains /jobs/ (may be correct for this company)")
        else:
            print(f"   ✅ Clean direct pattern")
    
    if len(jobs) > 5:
        print(f"\n   ... and {len(jobs) - 5} more jobs")
    
    # Step 3: Store in database
    print(f"\n\nSTEP 3: STORING IN DATABASE")
    print("-"*80)
    
    stored_count = 0
    for job in jobs[:3]:  # Store first 3 for testing
        try:
            print(f"\nStoring: {job['title']}")
            print(f"  External ID: {job['external_id']}")
            print(f"  URL to store: {job['url']}")
            
            insert_query = """
            INSERT INTO jobs 
            (source_id, external_id, title, company, location, department,
             description, job_type, url, posting_date, is_active, crawled_at)
            VALUES 
            (:source_id, :external_id, :title, :company, :location, :department,
             :description, :job_type, :url, :posting_date, TRUE, NOW())
            ON DUPLICATE KEY UPDATE
                last_updated = NOW()
            """
            
            job_id = execute_insert(insert_query, {
                "source_id": source_id,
                "external_id": job.get('external_id'),
                "title": job.get('title'),
                "company": company_name,
                "location": job.get('location'),
                "department": job.get('department'),
                "description": job.get('description', ''),
                "job_type": job.get('job_type', 'unknown'),
                "url": job.get('url'),
                "posting_date": job.get('posting_date')
            })
            
            stored_count += 1
            print(f"  ✅ Stored with ID: {job_id}")
            
        except Exception as e:
            print(f"  ❌ Error storing: {e}")
    
    print(f"\n✅ Stored {stored_count} jobs")
    
    # Step 4: Read back from database
    print(f"\n\nSTEP 4: READING FROM DATABASE")
    print("-"*80)
    
    db_jobs = execute_query("""
        SELECT id, title, company, external_id, url
        FROM jobs
        WHERE source_id = :source_id
        ORDER BY id DESC
        LIMIT 5
    """, {"source_id": source_id})
    
    for i, job in enumerate(db_jobs, 1):
        print(f"\n{i}. {job['title']}")
        print(f"   DB ID: {job['id']}")
        print(f"   External ID: {job['external_id']}")
        print(f"   URL in DB: {job['url']}")
        
        # Verify URL
        if '//jobs/' in job['url']:
            print(f"   ❌❌❌ STORED WITH DOUBLE SLASH!")
        elif '/jobs/' in job['url']:
            print(f"   ℹ️  Has /jobs/ in database")
        else:
            print(f"   ✅ Clean URL in database")
    
    print(f"\n\n{'='*80}")
    print(f"✅ DEBUG COMPLETE!")
    print(f"{'='*80}\n")

async def main():
    """Main function with menu"""
    
    companies = [
        ("Hedra", "https://jobs.ashbyhq.com/hedra", 16),
        ("AtoB", "https://jobs.ashbyhq.com/atob", 15),
        ("Pylon", "https://jobs.ashbyhq.com/pylon-labs", 5),
    ]
    
    print("\n🔍 Interactive Ashby Crawler Debug")
    print("="*80)
    print("\nSelect a company to debug:")
    for i, (name, url, _) in enumerate(companies, 1):
        print(f"  {i}. {name} - {url}")
    
    choice = input("\nEnter number (1-3) or press Enter for Hedra: ").strip()
    
    if not choice:
        choice = "1"
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(companies):
            name, url, source_id = companies[idx]
            await debug_crawl_and_store(name, url, source_id)
        else:
            print("Invalid choice!")
    except ValueError:
        print("Invalid input!")

if __name__ == '__main__':
    asyncio.run(main())
















#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl all AshbyHQ companies from startups_sf.json
"""

import sys
import os
import asyncio
import json
import logging

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backend.app.services.crawler.ashby import crawl_ashby

async def crawl_all(companies: list) -> list:
    """Loop through all companies in JSON array"""
    all_jobs = []
    
    for company in companies:
        careers_url = company.get("careers_url", "")
        
        if not careers_url or "ashbyhq.com" not in careers_url:
            logger.info(f"⏭️  Skipping {company['name']} (no AshbyHQ URL)")
            continue
        
        try:
            jobs = await crawl_ashby(careers_url)
            
            for job in jobs:
                job["company_name"] = company["name"]
                job["notes"] = company.get("notes", "")
                all_jobs.append(job)
                
        except Exception as e:
            logger.error(f"❌ Error crawling {company['name']}: {e}")
            continue
    
    return all_jobs

async def main():
    """Main function"""
    # Load companies from JSON
    json_path = os.path.join(os.path.dirname(__file__), "../../data/startups_sf.json")
    
    logger.info(f"📂 Loading companies from: {json_path}\n")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        companies_json = json.load(f)
    
    logger.info(f"📋 Found {len(companies_json)} companies in JSON\n")
    logger.info("="*80 + "\n")
    
    # Crawl all
    all_results = await crawl_all(companies_json)
    
    logger.info("\n" + "="*80)
    logger.info(f"📊 SUMMARY")
    logger.info("="*80)
    logger.info(f"Total jobs found: {len(all_results)}")
    
    # Group by company
    by_company = {}
    for job in all_results:
        company = job.get("company_name", "Unknown")
        by_company[company] = by_company.get(company, 0) + 1
    
    logger.info(f"\nJobs by company:")
    for company, count in sorted(by_company.items(), key=lambda x: -x[1]):
        logger.info(f"  • {company}: {count} jobs")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "../../data/crawled_jobs.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\n💾 Saved results to: {output_path}")
    
    # Show sample jobs
    logger.info(f"\n📋 Sample jobs:")
    for i, job in enumerate(all_results[:5], 1):
        logger.info(f"\n{i}. {job['title']}")
        logger.info(f"   Company: {job['company_name']}")
        logger.info(f"   Department: {job.get('department', 'N/A')}")
        logger.info(f"   Location: {job['location']}")
        logger.info(f"   URL: {job['url']}")

if __name__ == '__main__':
    asyncio.run(main())
















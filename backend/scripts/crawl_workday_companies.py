#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl all Workday companies from workday_startups.json
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

from backend.app.services.crawler.workday import crawl_workday

async def crawl_all_workday(companies: list) -> list:
    """Crawl all Workday companies"""
    all_jobs = []
    
    total = len(companies)
    logger.info(f"Starting to crawl {total} Workday companies...\n")
    
    for idx, company in enumerate(companies, 1):
        careers_url = company.get("careers_url", "")
        company_name = company.get("name", "Unknown")
        
        if not careers_url:
            logger.info(f"[{idx}/{total}] Skipping {company_name} (no careers URL)")
            continue
        
        try:
            logger.info(f"[{idx}/{total}] Crawling {company_name}...")
            jobs = await crawl_workday(careers_url)
            
            for job in jobs:
                job["company_name"] = company_name
                job["notes"] = company.get("notes", "")
                job["location_type"] = company.get("location_type", "")
                all_jobs.append(job)
            
            logger.info(f"           Found {len(jobs)} jobs")
                
        except Exception as e:
            logger.error(f"           Error: {e}")
            continue
    
    return all_jobs

async def main():
    """Main function"""
    # Load Workday companies from JSON
    json_path = os.path.join(os.path.dirname(__file__), "../../data/workday_startups.json")
    
    logger.info("="*80)
    logger.info("WORKDAY COMPANY CRAWLER")
    logger.info("="*80)
    logger.info(f"Loading companies from: {json_path}\n")
    
    # Check if file exists
    if not os.path.exists(json_path):
        logger.error(f"File not found: {json_path}")
        logger.info("No Workday companies to crawl.")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        companies_json = json.load(f)
    
    if not companies_json:
        logger.info("No Workday companies found in JSON file.")
        return
    
    logger.info(f"Found {len(companies_json)} Workday companies\n")
    logger.info("="*80 + "\n")
    
    # Crawl all
    all_results = await crawl_all_workday(companies_json)
    
    logger.info("\n" + "="*80)
    logger.info("CRAWL SUMMARY")
    logger.info("="*80)
    logger.info(f"Total jobs found: {len(all_results)}")
    
    # Group by company
    by_company = {}
    for job in all_results:
        company = job.get("company_name", "Unknown")
        by_company[company] = by_company.get(company, 0) + 1
    
    logger.info(f"\nJobs by company:")
    for company, count in sorted(by_company.items(), key=lambda x: -x[1]):
        logger.info(f"  {company}: {count} jobs")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "../../data/workday_crawled_jobs.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\nSaved results to: {output_path}")
    logger.info("="*80)

if __name__ == '__main__':
    asyncio.run(main())











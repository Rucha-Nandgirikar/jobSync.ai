#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl all AshbyHQ companies and print JSON output
"""

import sys
import os
import asyncio
import json

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.services.crawler.ashby import crawl_ashby

async def crawl_all(companies: list) -> list:
    """Loop through all companies in JSON array"""
    all_jobs = []
    
    for company in companies:
        careers_url = company.get("careers_url", "")
        
        if not careers_url or "ashbyhq.com" not in careers_url:
            print(f"⏭️  Skipping {company['name']} (no AshbyHQ URL)", file=sys.stderr)
            continue
        
        try:
            jobs = await crawl_ashby(careers_url)
            
            for job in jobs:
                job["company_name"] = company["name"]
                job["notes"] = company.get("notes", "")
                all_jobs.append(job)
                
        except Exception as e:
            print(f"❌ Error crawling {company['name']}: {e}", file=sys.stderr)
            continue
    
    return all_jobs

async def main():
    """Main function"""
    # Load companies from JSON
    json_path = os.path.join(os.path.dirname(__file__), '../../data/startups_sf.json')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        companies_json = json.load(f)
    
    # Crawl all
    all_results = await crawl_all(companies_json)
    
    # Print JSON output (this is what you asked for!)
    print(json.dumps(all_results, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
















#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug the FULL flow from crawler to database
"""

import sys
import os
import asyncio

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Patch the crawler to add extreme debugging
import backend.app.services.crawler.ashby as ashby_module

original_crawl = ashby_module.crawl_ashby

async def debug_crawl(base_url):
    print(f"\n{'='*80}")
    print(f"STARTING CRAWL: {base_url}")
    print('='*80)
    
    jobs = await original_crawl(base_url)
    
    print(f"\n{'='*80}")
    print(f"CRAWL RESULT - Found {len(jobs)} jobs")
    print('='*80)
    
    for i, job in enumerate(jobs[:3], 1):
        print(f"\n{i}. {job['title']}")
        print(f"   external_id: {job['external_id']}")
        print(f"   url: {job['url']}")
        
        # Check for issues
        if '//jobs/' in job['url']:
            print(f"   ❌❌❌ ERROR: URL has '//jobs/'")
        elif '/jobs/' in job['url']:
            print(f"   ⚠️  WARNING: URL has '/jobs/' (single slash)")
        else:
            print(f"   ✅ URL looks good")
    
    return jobs

ashby_module.crawl_ashby = debug_crawl

# Now test the full flow
async def test_full_flow():
    from backend.app.services.crawler import crawl_source
    
    # Test with a specific source
    print("\n" + "="*80)
    print("TESTING FULL FLOW: crawl_source()")
    print("="*80)
    
    # You need to have a source_id for hedra or atob in your database
    # Check your job_sources table for the ID
    source_id = 1  # Change this to an actual source_id from your database
    
    print(f"\nCalling crawl_source({source_id})...")
    result = await crawl_source(source_id)
    
    print(f"\n{'='*80}")
    print(f"FINAL RESULT")
    print('='*80)
    print(f"Status: {result.get('status')}")
    print(f"New jobs: {result.get('new_count')}")
    print(f"Updated jobs: {result.get('updated_count')}")

if __name__ == '__main__':
    # First test just the crawler
    asyncio.run(debug_crawl("https://jobs.ashbyhq.com/hedra"))
















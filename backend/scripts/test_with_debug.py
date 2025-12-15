#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Ashby crawler with DEBUG logging
"""

import sys
import os
import asyncio
import logging

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging to show DEBUG messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

from app.services.crawler.ashby import crawl_ashby

async def test():
    """Test with debug logging"""
    
    test_url = "https://jobs.ashbyhq.com/atob"
    
    print(f"\n{'='*80}")
    print(f"TESTING: {test_url} with DEBUG logging")
    print('='*80 + "\n")
    
    jobs = await crawl_ashby(test_url)
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print('='*80)
    print(f"Total jobs found: {len(jobs)}\n")
    
    if jobs:
        print("First 3 jobs:")
        for i, job in enumerate(jobs[:3], 1):
            print(f"\n{i}. {job['title']}")
            print(f"   External ID: {job['external_id']}")
            print(f"   URL: {job['url']}")
            
            # Check for issues
            if '//jobs/' in job['url']:
                print(f"   ❌ ERROR: URL contains '//jobs/'")
            elif '/jobs/' in job['url']:
                print(f"   ❌ ERROR: URL contains '/jobs/'")
            else:
                print(f"   ✅ URL format correct")

if __name__ == '__main__':
    asyncio.run(test())
















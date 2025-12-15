#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Ashby crawler
"""

import sys
import os
import asyncio

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.crawler.ashby import crawl_ashby

async def test_crawl():
    """Test crawling an Ashby job board"""
    
    # Test URLs
    test_urls = [
        "https://jobs.ashbyhq.com/atob",
        "https://jobs.ashbyhq.com/pylon-labs",
    ]
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Testing: {url}")
        print('='*80)
        
        try:
            jobs = await crawl_ashby(url)
            
            if jobs:
                print(f"\n✅ Successfully crawled {len(jobs)} jobs!\n")
                
                # Display first 5 jobs
                for i, job in enumerate(jobs[:5], 1):
                    print(f"{i}. {job['title']}")
                    print(f"   🏢 Company: {job['company']}")
                    print(f"   📍 Location: {job['location']}")
                    print(f"   🏷️  Department: {job['department']}")
                    print(f"   🔗 URL: {job['url']}")
                    print()
                
                if len(jobs) > 5:
                    print(f"   ... and {len(jobs) - 5} more jobs")
            else:
                print(f"\n❌ No jobs found")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    print("\n🚀 Testing Ashby Crawler...\n")
    asyncio.run(test_crawl())
    print("\n✅ Test complete!\n")


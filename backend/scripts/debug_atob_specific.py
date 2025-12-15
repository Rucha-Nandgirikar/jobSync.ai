#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug specific atob job URL with //jobs/ issue
"""

import sys
import os
import asyncio

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse

async def debug_atob():
    """Debug atob URL extraction"""
    
    test_url = "https://jobs.ashbyhq.com/atob"
    target_id = "3cf7c15b-760d-44ca-a464-e2e5a364b19b"
    
    print(f"\n🔍 Debugging URL for job ID: {target_id}")
    print(f"   Base URL: {test_url}\n")
    
    parsed_url = urlparse(test_url)
    company_slug = parsed_url.path.strip('/').split('/')[-1]
    print(f"Company slug: {company_slug}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Loading page...")
        await page.goto(test_url, wait_until="networkidle", timeout=90000)
        html_content = await page.content()
        
        # Also extract JSON
        app_data = None
        try:
            app_data = await page.evaluate("""
                () => {
                    if (window.__appData) {
                        return window.__appData;
                    }
                    return null;
                }
            """)
        except Exception as e:
            print(f"Could not extract window.__appData: {e}")
        
        await browser.close()
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    print("=" * 80)
    print("SEARCHING FOR TARGET JOB IN HTML:")
    print("=" * 80)
    
    found_in_html = False
    for link in soup.find_all("a", href=True):
        href = link["href"]
        
        if target_id in href:
            found_in_html = True
            title = link.get_text(strip=True)
            
            print(f"\n✅ FOUND IN HTML!")
            print(f"   Title: {title}")
            print(f"   Raw href: {href}")
            print(f"   Has '/jobs/': {'YES ❌' if '/jobs/' in href else 'NO ✅'}")
            
            # What our code would do
            url_parts = href.strip('/').split('/')
            print(f"   URL parts after split: {url_parts}")
            
            if len(url_parts) >= 2:
                external_id = url_parts[-1]
                print(f"   External ID extracted: {external_id}")
                constructed_url = f"{test_url.rstrip('/')}/{external_id}"
                print(f"   CONSTRUCTED URL: {constructed_url}")
    
    if not found_in_html:
        print(f"\n❌ Job ID {target_id} NOT FOUND in HTML links")
    
    # Check JSON
    if app_data:
        print("\n" + "=" * 80)
        print("SEARCHING FOR TARGET JOB IN JSON:")
        print("=" * 80)
        
        job_postings = app_data.get('jobBoard', {}).get('jobPostings', [])
        print(f"Total postings in JSON: {len(job_postings)}")
        
        for posting in job_postings:
            job_id = posting.get('id')
            if job_id == target_id or target_id in str(posting):
                print(f"\n✅ FOUND IN JSON!")
                print(f"   ID: {job_id}")
                print(f"   Title: {posting.get('title')}")
                
                # Check all fields for any URL
                for key, value in posting.items():
                    if 'url' in key.lower() or (isinstance(value, str) and 'http' in value):
                        print(f"   {key}: {value}")
                
                # What our code would construct
                constructed = f"{test_url.rstrip('/')}/{job_id}"
                print(f"   CONSTRUCTED URL: {constructed}")
    
    # Show ALL links with /jobs/ in them
    print("\n" + "=" * 80)
    print("ALL LINKS WITH /jobs/ IN HREF:")
    print("=" * 80)
    
    jobs_links = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if '/jobs/' in href:
            jobs_links.append(href)
    
    if jobs_links:
        print(f"\n❌ Found {len(jobs_links)} links with '/jobs/':")
        for href in jobs_links[:5]:
            print(f"   {href}")
    else:
        print("\n✅ NO links with '/jobs/' found!")

if __name__ == '__main__':
    asyncio.run(debug_atob())
















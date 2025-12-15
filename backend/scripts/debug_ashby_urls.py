#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug Ashby URLs - check what hrefs we're getting from HTML
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

async def debug_urls():
    """Debug URL extraction from Ashby"""
    
    test_url = "https://jobs.ashbyhq.com/pylon-labs"
    
    print(f"\n🔍 Debugging URL extraction from: {test_url}\n")
    
    parsed_url = urlparse(test_url)
    company_slug = parsed_url.path.strip('/').split('/')[-1]
    print(f"Company slug: {company_slug}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(test_url, wait_until="networkidle", timeout=90000)
        html_content = await page.content()
        await browser.close()
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    print("=" * 80)
    print("CHECKING ALL <a> TAGS WITH COMPANY SLUG IN HREF:")
    print("=" * 80)
    
    count = 0
    for link in soup.find_all("a", href=True):
        href = link["href"]
        
        if f"/{company_slug}/" in href:
            count += 1
            title = link.get_text(strip=True)
            
            print(f"\n{count}. TITLE: {title}")
            print(f"   RAW HREF: {href}")
            print(f"   Has '/jobs/': {'YES ❌' if '/jobs/' in href else 'NO ✅'}")
            print(f"   Has '/apply': {'YES' if '/apply' in href else 'NO'}")
            
            # Extract external_id
            url_parts = href.strip('/').split('/')
            if len(url_parts) >= 2:
                external_id = url_parts[-1]
                print(f"   External ID: {external_id}")
                
                # Show what our code would construct
                constructed_url = f"{test_url.rstrip('/')}/{external_id}"
                print(f"   CONSTRUCTED URL: {constructed_url}")
            
            if count >= 5:
                print("\n... (stopping after 5 for brevity)")
                break

if __name__ == '__main__':
    asyncio.run(debug_urls())
















#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import asyncio

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

async def test_hedra():
    url = "https://jobs.ashbyhq.com/hedra"
    
    print(f"Testing: {url}\n")
    
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    company_slug = parsed.path.strip("/")
    
    print(f"Origin: {origin}")
    print(f"Company slug: {company_slug}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=90000)
        html = await page.content()
        await browser.close()
    
    soup = BeautifulSoup(html, "html.parser")
    
    print("="*80)
    print("FIRST 5 HREF VALUES FROM HTML:")
    print("="*80)
    
    count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        
        if company_slug in href and "/apply" not in href:
            count += 1
            print(f"\n{count}. RAW HREF: {href}")
            
            parts = [p for p in href.strip("/").split("/") if p]
            print(f"   Parts: {parts}")
            print(f"   len(parts): {len(parts)}")
            if len(parts) >= 2:
                print(f"   parts[1]: {parts[1] if len(parts) > 1 else 'N/A'}")
            print(f"   parts[-1] (external_id): {parts[-1]}")
            
            # Show what the code would construct
            external_id = parts[-1]
            if len(parts) >= 3 and parts[1] == "jobs":
                job_url = urljoin(origin, f"/{company_slug}/{external_id}")
                print(f"   CONSTRUCTED (if branch): {job_url}")
            else:
                job_url = urljoin(origin, f"/{company_slug}/{external_id}")
                print(f"   CONSTRUCTED (else branch): {job_url}")
            
            # Check for issues
            if '//jobs/' in job_url:
                print(f"   ❌❌❌ ERROR: Has //jobs/")
            elif '/jobs/' in job_url:
                print(f"   ⚠️  Has /jobs/ (single)")
            else:
                print(f"   ✅ Clean")
            
            if count >= 5:
                break

asyncio.run(test_hedra())
















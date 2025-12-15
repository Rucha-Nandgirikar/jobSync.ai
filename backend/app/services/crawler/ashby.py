import logging
from typing import List, Dict, Any
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def crawl_ashby(base_url: str) -> List[Dict[str, Any]]:
    """Crawl a single AshbyHQ company job board"""
    jobs = []
    
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    company_slug = parsed.path.strip("/")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        logger.info(f"🌐 Crawling {base_url} ...")
        await page.goto(base_url, wait_until="networkidle", timeout=90000)
        
        # Extract rendered HTML + appData
        html = await page.content()
        try:
            app_data = await page.evaluate("() => window.__appData || null")
        except:
            app_data = None
        
        await browser.close()
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Mapping id → posting metadata
    id_to_posting = {}
    if isinstance(app_data, dict):
        postings = app_data.get("jobBoard", {}).get("jobPostings", [])
        for p in postings:
            pid = p.get("id")
            if pid:
                id_to_posting[pid] = p
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        
        if "/apply" in href or company_slug not in href:
            continue
        
        parts = [p for p in href.strip("/").split("/") if p]
        if not parts or len(parts[-1]) < 20:
            continue
        
        external_id = parts[-1]
        
        # Detect `/jobs/` pattern dynamically
        if len(parts) >= 3 and parts[1] == "jobs":
            job_url = urljoin(origin, f"/{company_slug}/jobs/{external_id}")
            logger.debug(f"Using /jobs/ pattern: {job_url}")
        else:
            job_url = urljoin(origin, f"/{company_slug}/{external_id}")
            logger.debug(f"Using direct pattern: {job_url}")
        
        posting = id_to_posting.get(external_id, {})
        
        title = posting.get("title") or a.get_text(strip=True)
        if not title:
            continue
        
        department = posting.get("departmentName") or posting.get("teamName")
        location = posting.get("locationName") or "Remote"
        
        if posting.get("secondaryLocations"):
            sec = posting["secondaryLocations"][0].get("locationName", "")
            if sec:
                location = f"{location}, {sec}"
        
        job_type = "full_time" if posting.get("employmentType") == "FullTime" else "unknown"
        posting_date = posting.get("publishedDate")
        
        job_data = {
            "company": company_slug,
            "external_id": external_id,
            "title": title,
            "department": department,
            "location": location,
            "description": "",  # Added for database compatibility
            "job_type": job_type,
            "url": job_url,
            "posting_date": posting_date,
        }
        
        jobs.append(job_data)
        logger.info(f"✅ {title}")
        logger.info(f"   URL: {job_url}")
    
    logger.info(f"🎯 Found {len(jobs)} jobs from {company_slug}")
    return jobs

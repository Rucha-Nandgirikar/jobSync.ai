import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

async def crawl_lever(base_url: str) -> List[Dict[str, Any]]:
    """Crawl Lever job board"""
    jobs = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Placeholder: Adjust selectors based on actual Lever structure
            job_items = soup.find_all('div', class_='posting')
            
            for item in job_items:
                try:
                    title = item.find('a', class_='posting-title')
                    location = item.find('span', class_='posting-location')
                    company = item.find('span', class_='company-name')
                    
                    job_data = {
                        "external_id": item.get('data-job-id'),
                        "title": title.text.strip() if title else "N/A",
                        "company": company.text.strip() if company else "N/A",
                        "location": location.text.strip() if location else "Remote",
                        "description": item.get_text(),
                        "job_type": "full_time",
                        "url": title['href'] if title and title.has_attr('href') else base_url,
                        "posting_date": None
                    }
                    jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error parsing Lever job: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Lever crawl error: {e}")
    
    return jobs



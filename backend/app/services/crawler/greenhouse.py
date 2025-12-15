import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

async def crawl_greenhouse(base_url: str) -> List[Dict[str, Any]]:
    """Crawl Greenhouse job board"""
    jobs = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Placeholder: Adjust selectors based on actual Greenhouse structure
            job_items = soup.find_all('div', class_='job-item')
            
            for item in job_items:
                try:
                    title_elem = item.find('h4')
                    location_elem = item.find('span', class_='location')
                    link = item.find('a')
                    
                    job_data = {
                        "external_id": item.get('data-job-id'),
                        "title": title_elem.text.strip() if title_elem else "N/A",
                        "company": "Greenhouse",
                        "location": location_elem.text.strip() if location_elem else "Remote",
                        "description": item.get_text(),
                        "job_type": "full_time",
                        "url": link['href'] if link and link.has_attr('href') else base_url,
                        "posting_date": None
                    }
                    jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error parsing Greenhouse job: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Greenhouse crawl error: {e}")
    
    return jobs



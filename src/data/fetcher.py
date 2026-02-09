import httpx
import os
import logging
from typing import List, Dict, Optional

from ddgs import DDGS

# --- Logging Configuration ---
logger = logging.getLogger("WebFetcher")

# --- WebPerceptor Configuration ---
WEB_PERCEPTOR_URL = os.getenv("WEB_PERCEPTOR_URL", "http://localhost:8011/render")

async def render_page_deep(url: str, timeout: int = 15000) -> Optional[Dict]:
    """
    Calls the WebPerceptor service to deeply render a page and get structured content.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WEB_PERCEPTOR_URL,
                json={"url": url, "timeout": timeout},
                timeout=timeout / 1000 + 5  # Add a buffer to the HTTP timeout
            )
            response.raise_for_status()
            logger.info(f"Successfully rendered URL via WebPerceptor: {url}")
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to WebPerceptor service for URL {url}: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"WebPerceptor service returned error for URL {url}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling WebPerceptor for {url}: {e}")
        return None

def search_web_ddg(query: str, max_results: int = 3) -> List[Dict]:
    """
    Performs a web search using DuckDuckGo and returns a list of result dictionaries.
    Note: The 'body' in these results is from a simple scrape, not deep rendering.
    """
    if not query or not query.strip():
        logger.warning("Web search requested with empty query.")
        return []

    logger.info(f"Performing DDG web search for: '{query}'")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            logger.info("No results found from DDG web search.")
            return []
            
        logger.info(f"Retrieved {len(results)} search results from DDG.")
        return results

    except Exception as e:
        logger.error(f"An error occurred during the DDG web search: {e}", exc_info=True)
        return []

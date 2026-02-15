import os
import httpx
import logging
from typing import Optional, List
from pydantic import BaseModel

from ..utils.utils import extract_links

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- WebPerceptor Configuration ---
WEB_PERCEPTOR_URL = os.getenv("WEB_PERCEPTOR_URL", "http://localhost:8011/render")

class RenderResponse(BaseModel):
    url: str
    body: str
    hrefs: List[str]

async def render_page_deep(url: str, timeout: int = 15000) -> Optional[RenderResponse]:
    """
    Calls the WebPerceptor service to deeply render a page.
    Returns a RenderResponse object containing the URL, body HTML, and extracted links.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WEB_PERCEPTOR_URL,
                json={"url": url, "timeout": timeout},
                timeout=timeout / 1000 + 5  # Add a buffer to the HTTP timeout
            )
            response.raise_for_status()
            data = response.json()
            
            body_html = data.get("body", "")
            
            # If the service returns hrefs, use them. Otherwise, extract them here.
            hrefs = data.get("hrefs")
            if hrefs is None:
                # Extract links from the body if not provided by the service
                hrefs = list(extract_links(body_html, url))
            
            logger.info(f"Successfully rendered URL via WebPerceptor: {url}")
            
            return RenderResponse(
                url=data.get("url", url),
                body=body_html,
                hrefs=hrefs
            )

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to WebPerceptor service for URL {url}: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"WebPerceptor service returned error for URL {url}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling WebPerceptor for {url}: {e}")
        return None

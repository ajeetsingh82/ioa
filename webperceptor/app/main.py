import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebPerceptor")

# --- Pydantic Models ---
class RenderRequest(BaseModel):
    url: HttpUrl
    timeout: int = 15000

class RenderResponse(BaseModel):
    url: HttpUrl
    body: str = Field(..., description="The HTML content of the <body> tag.")
    hrefs: List[str] = Field(..., description="A list of all absolute URLs found in anchor tags.")

# --- FastAPI App Lifecycle ---
playwright_instance = None
browser = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright_instance, browser
    logger.info("Starting Playwright...")
    try:
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(headless=True)
        logger.info("Playwright started and Chromium browser launched.")
        yield
    finally:
        if browser:
            await browser.close()
            logger.info("Chromium browser closed.")
        if playwright_instance:
            await playwright_instance.stop()
            logger.info("Playwright stopped.")

# --- FastAPI App ---
app = FastAPI(
    title="WebPerceptor",
    description="A service to render web pages and extract structured body content.",
    lifespan=lifespan
)

# --- API Endpoints ---
@app.get("/health", status_code=200)
async def health_check():
    return {"status": "ok"}

@app.post("/render", response_model=RenderResponse)
async def render_page(request: RenderRequest):
    page = None
    try:
        page = await browser.new_page()
        
        await page.goto(str(request.url), timeout=request.timeout, wait_until="networkidle")
        
        html_content = await page.content()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        body = soup.find('body')
        if not body:
            return RenderResponse(url=request.url, body="", hrefs=[])

        # Extract all hrefs and make them absolute
        hrefs = []
        for a_tag in body.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('http'):
                hrefs.append(href)
            elif href.startswith('/'):
                # Construct absolute URL from relative path
                base_url = f"{request.url.scheme}://{request.url.host}"
                hrefs.append(base_url + href)

        # Remove script, style, and other non-content tags from the body
        for tag in body(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
            
        # Get the HTML content of the cleaned body
        body_html = str(body)
        
        logger.info(f"Successfully rendered and extracted body from {request.url}")
        
        return RenderResponse(
            url=request.url,
            body=body_html,
            hrefs=hrefs
        )

    except PlaywrightTimeoutError:
        logger.warning(f"Timeout error while rendering {request.url}")
        return RenderResponse(url=request.url, body="", hrefs=[])
    except Exception as e:
        logger.error(f"An unexpected error occurred while rendering {request.url}: {e}", exc_info=True)
        return RenderResponse(url=request.url, body="", hrefs=[])
    finally:
        if page:
            await page.close()

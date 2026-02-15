from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from .crawler import crawler_service
from .data.ledger import ledger, LedgerNamespace

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IOA Web Crawler Service")

class CrawlRequest(BaseModel):
    urls: List[str]

@app.on_event("startup")
async def startup_event():
    logger.info("Starting crawler worker...")
    await crawler_service.start_worker()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down crawler service...")
    await crawler_service.close()

@app.post("/crawl")
async def crawl_endpoint(request: CrawlRequest):
    """
    Accepts a list of URLs and adds them to the crawl queue.
    Returns immediately with a confirmation.
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided.")

    try:
        # Push URLs to the Redis queue
        num_added = ledger.lpush(LedgerNamespace.CRAWL_QUEUE, *request.urls)
        logger.info(f"Added {num_added} URLs to the crawl queue.")
        return {"status": "queued", "count": num_added}
    except Exception as e:
        logger.exception("Failed to queue URLs for crawling.")
        raise HTTPException(status_code=500, detail=str(e))

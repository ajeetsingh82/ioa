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
    await crawler_service.start()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down crawler service...")
    await crawler_service.stop()

@app.post("/crawl")
async def crawl_endpoint(request: CrawlRequest):
    """
    Accepts a list of URLs and adds them to the crawl queue.
    Returns immediately with a confirmation.

    Example:
    ```bash
    curl -X POST "http://localhost:8002/crawl" \
         -H "Content-Type: application/json" \
         -d '{
               "urls": ["https://www.wikipedia.org/", "https://timesofindia.indiatimes.com/"]
             }'
    ```
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

@app.post("/clear-queue")
async def clear_queue_endpoint():
    """
    Clears the pending crawl queue.

    Example:
    ```bash
    curl -X POST "http://localhost:8002/clear-queue"
    ```
    """
    try:
        ledger.delete(LedgerNamespace.CRAWL_QUEUE)
        logger.info("Cleared crawl queue.")
        return {"status": "cleared"}
    except Exception as e:
        logger.exception("Failed to clear crawl queue.")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue-size")
async def queue_size_endpoint():
    """
    Returns the current number of items in the crawl queue.

    Example:
    ```bash
    curl -X GET "http://localhost:8002/queue-size"
    ```
    """
    try:
        size = ledger.llen(LedgerNamespace.CRAWL_QUEUE)
        return {"queue_size": size}
    except Exception as e:
        logger.exception("Failed to get queue size.")
        raise HTTPException(status_code=500, detail=str(e))

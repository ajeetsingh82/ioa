import asyncio
import logging
import hashlib
import time
import json
from typing import List, Dict, Set
from urllib.parse import urlparse
from collections import defaultdict

from .data.memory import memory
from .data.crawling_ledger import crawling_ledger
from .data.documents import NamespaceBuilder
from .data.ledger import ledger, LedgerNamespace
from .data.fetcher import render_page_deep, RenderResponse
from .utils.utils import try_extract_text_from_html, split_text

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
MAX_CONCURRENCY = 10
DOMAIN_RATE_LIMIT = 1.0  # Seconds between requests to the same domain
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

class Crawler:
    def __init__(self):
        self._shutdown = False
        self.worker_tasks = []
        # Rate limiting: Semaphore per domain to limit concurrency
        self.domain_semaphores = defaultdict(lambda: asyncio.Semaphore(1))
        # Last request time per domain to enforce delay
        self.last_request_time = defaultdict(float)

    async def start_worker(self, concurrency: int = MAX_CONCURRENCY):
        """Starts multiple background worker tasks."""
        if not self.worker_tasks:
            self._shutdown = False
            self.worker_tasks = [
                asyncio.create_task(self.worker(i)) 
                for i in range(concurrency)
            ]
            logger.info(f"Crawler started with {concurrency} workers.")

    async def stop_worker(self):
        """Stops all background worker tasks."""
        if self.worker_tasks:
            self._shutdown = True
            # Push enough shutdown signals for all workers
            for _ in self.worker_tasks:
                ledger.lpush(LedgerNamespace.CRAWL_QUEUE, "shutdown")
            
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.worker_tasks = []
            logger.info("Crawler workers stopped.")

    async def close(self):
        await self.stop_worker()

    async def worker(self, worker_id: int):
        """The main worker loop that processes URLs from the queue."""
        loop = asyncio.get_running_loop()
        logger.debug(f"Worker {worker_id} started.")
        
        while not self._shutdown:
            try:
                # Use run_in_executor to prevent blocking the event loop with synchronous Redis call
                result = await loop.run_in_executor(
                    None, 
                    ledger.brpop, 
                    [LedgerNamespace.CRAWL_QUEUE], 
                    1
                )
                
                if result is None:
                    continue # Timeout, loop again

                _, url = result
                if url == "shutdown":
                    break

                logger.info(f"Worker {worker_id} picked up URL: {url}")
                await self._process_url(url)

            except Exception as e:
                logger.exception(f"Error in crawler worker {worker_id}: {e}")
                await asyncio.sleep(1) # Avoid fast-spinning on persistent errors

    def _hash_url(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def _process_url(self, url: str, freshness_window: int = 86400) -> Dict:
        """
        Process a single URL: Check Ledger -> Rate Limit -> Fetch (Retry) -> Parse -> Store -> Expand.
        """
        domain = self._get_domain(url)
        
        try:
            # 1. Check Ledger (Fast check before locking)
            if crawling_ledger.has_been_crawled(url, freshness_window):
                logger.info(f"Skipping {url}: Fresh enough.")
                return {"url": url, "status": "skipped", "reason": "fresh"}

            # 2. Claim Lock (Atomic check to prevent duplicate processing)
            if not crawling_ledger.claim_for_crawling(url):
                logger.info(f"Skipping {url}: Locked by another crawler.")
                return {"url": url, "status": "skipped", "reason": "locked"}

            crawling_ledger.mark_in_progress(url)

            # 3. Rate Limiting & Politeness
            async with self.domain_semaphores[domain]:
                # Enforce delay since last request to this domain
                now = time.time()
                elapsed = now - self.last_request_time[domain]
                if elapsed < DOMAIN_RATE_LIMIT:
                    delay = DOMAIN_RATE_LIMIT - elapsed
                    logger.debug(f"Rate limiting {domain}: sleeping {delay:.2f}s")
                    await asyncio.sleep(delay)
                
                self.last_request_time[domain] = time.time()

                # 4. Fetch with Retries
                render_response: RenderResponse = None
                for attempt in range(MAX_RETRIES):
                    try:
                        logger.info(f"Fetching {url} (Attempt {attempt + 1}/{MAX_RETRIES})...")
                        render_response = await render_page_deep(url)
                        
                        if render_response and render_response.body:
                            break # Success
                        else:
                            logger.warning(f"Empty body for {url} on attempt {attempt + 1}")
                    except Exception as e:
                        logger.warning(f"Fetch error for {url} on attempt {attempt + 1}: {e}")
                    
                    if attempt < MAX_RETRIES - 1:
                        backoff = RETRY_BACKOFF_BASE ** attempt
                        await asyncio.sleep(backoff)

                if not render_response or not render_response.body:
                    error_msg = "Failed to fetch content after retries."
                    crawling_ledger.mark_failed(url, error_msg)
                    return {"url": url, "status": "failed", "error": error_msg}

            # 5. Parse Content
            html = render_response.body
            clean_text = try_extract_text_from_html(html)
            if not clean_text:
                crawling_ledger.mark_failed(url, "Empty or invalid content after parsing")
                return {"url": url, "status": "failed", "error": "empty_content"}

            # 6. Store in Memory (Chroma) - WITH CHUNKING
            # Use stable content hash for deduplication of the whole page
            full_content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
            base_doc_id = self._hash_url(url)
            namespace = NamespaceBuilder.global_data(path=["scout", "crawler"])
            
            # Split text into chunks
            chunks = split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            
            if not chunks:
                logger.warning(f"No chunks generated for {url}")
                return {"url": url, "status": "failed", "error": "no_chunks"}

            chunk_ids = []
            chunk_metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{base_doc_id}_chunk_{i}"
                chunk_ids.append(chunk_id)
                chunk_metadatas.append({
                    "source": url,
                    "namespace": namespace,
                    "content_hash": full_content_hash, # Hash of the full page
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                })

            memory.upsert(
                collection_name=namespace,
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )

            # 7. Link Discovery (Expansion)
            # Use hrefs from RenderResponse
            new_links = render_response.hrefs
            added_count = 0
            for link in new_links:
                # Basic check if already crawled to avoid queue bloat
                if not crawling_ledger.has_been_crawled(link, freshness_window):
                    # Push to queue
                    ledger.lpush(LedgerNamespace.CRAWL_QUEUE, link)
                    added_count += 1
            
            if added_count > 0:
                logger.info(f"Discovered {len(new_links)} links on {url}, queued {added_count} new ones.")

            # 8. Update Ledger
            crawling_ledger.mark_visited(url, content_hash=full_content_hash)
            logger.info(f"Successfully crawled and indexed {url} ({len(chunks)} chunks)")
            
            return {"url": url, "status": "success", "links_found": len(new_links), "chunks": len(chunks)}

        except Exception as e:
            logger.exception(f"Unexpected error processing {url}")
            crawling_ledger.mark_failed(url, str(e))
            return {"url": url, "status": "error", "error": str(e)}

crawler_service = Crawler()

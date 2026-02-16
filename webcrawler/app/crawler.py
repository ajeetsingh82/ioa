import asyncio
import logging
import hashlib
import time
from typing import Set
from urllib.parse import urlparse
from collections import defaultdict

from .data.memory import memory
from .data.crawling_ledger import crawling_ledger
from .data.documents import NamespaceBuilder
from .data.ledger import ledger, LedgerNamespace
from .data.fetcher import render_page_deep
from .utils.utils import try_extract_text_from_html, split_text

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ==============================
# CONFIG
# ==============================

MAX_CONCURRENCY = 10
DOMAIN_RATE_LIMIT = 1.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

REDIS_SEEN_URLS = "crawler:seen_urls"
REDIS_CHUNK_REFCOUNT = "crawler:chunk_refcount"

# 🔥 Backpressure Config
MAX_QUEUE_SIZE = 1000
INITIAL_QUEUE_WAIT = 0.5
MAX_QUEUE_WAIT = 5.0


# ============================================================
# PRODUCTION-GRADE CRAWLER (SMOOTH BACKPRESSURE)
# ============================================================

class Crawler:

    def __init__(self):
        self._shutdown = False
        self.worker_tasks = []
        self.domain_semaphores = defaultdict(lambda: asyncio.Semaphore(1))
        self.last_request_time = defaultdict(float)

    # ============================================================
    # Utilities
    # ============================================================

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip("/")

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _url_key(self, url: str) -> str:
        return f"crawler:url_chunks:{self._hash(url)}"

    def _queue_size(self) -> int:
        return ledger.llen(LedgerNamespace.CRAWL_QUEUE)

    async def _wait_for_queue_capacity(self):
        """
        Smooth exponential backpressure.
        No log spam.
        Reacts quickly when capacity frees.
        """
        sleep_time = INITIAL_QUEUE_WAIT

        while self._queue_size() > MAX_QUEUE_SIZE:
            await asyncio.sleep(sleep_time)
            sleep_time = min(sleep_time * 2, MAX_QUEUE_WAIT)

    # ============================================================
    # Worker Control
    # ============================================================

    async def start_worker(self, concurrency: int = MAX_CONCURRENCY):
        if not self.worker_tasks:
            self._shutdown = False
            self.worker_tasks = [
                asyncio.create_task(self.worker(i))
                for i in range(concurrency)
            ]

    async def stop_worker(self):
        if self.worker_tasks:
            self._shutdown = True
            for _ in self.worker_tasks:
                ledger.lpush(LedgerNamespace.CRAWL_QUEUE, "shutdown")

            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.worker_tasks = []

    async def worker(self, worker_id: int):
        loop = asyncio.get_running_loop()

        while not self._shutdown:
            result = await loop.run_in_executor(
                None,
                ledger.brpop,
                [LedgerNamespace.CRAWL_QUEUE],
                1
            )

            if not result:
                continue

            _, url = result

            if url == "shutdown":
                break

            try:
                await self._process_url(url)
            except Exception:
                logger.exception(f"Worker {worker_id} failed")

    # ============================================================
    # MAIN PROCESSOR
    # ============================================================

    async def _process_url(self, url: str, freshness_window: int = 86400):

        url = self._normalize_url(url)

        if crawling_ledger.has_been_crawled(url, freshness_window):
            return

        if not crawling_ledger.claim_for_crawling(url):
            return

        crawling_ledger.mark_in_progress(url)

        try:
            render_response = await self._rate_limited_fetch(url)

            if not render_response or not render_response.body:
                crawling_ledger.mark_failed(url, "fetch_failed")
                return

            text = try_extract_text_from_html(render_response.body)
            if not text:
                crawling_ledger.mark_failed(url, "empty_content")
                return

            text = " ".join(text.split())
            full_hash = self._hash(text)
            previous_hash = crawling_ledger.get_content_hash(url)

            namespace = NamespaceBuilder.global_data(
                path=["scout", "crawler"]
            )

            if previous_hash == full_hash:
                crawling_ledger.mark_visited(url, content_hash=full_hash)
                return

            url_key = self._url_key(url)
            old_chunks: Set[str] = ledger.smembers(url_key) or set()

            chunks = split_text(
                text,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP
            )

            new_chunks: Set[str] = {
                self._hash(chunk) for chunk in chunks
            }

            chunks_to_add = new_chunks - old_chunks
            chunks_to_remove = old_chunks - new_chunks

            # Remove old chunks
            for chunk_hash in chunks_to_remove:
                refcount = ledger.hincrby(
                    REDIS_CHUNK_REFCOUNT,
                    chunk_hash,
                    -1
                )

                if refcount <= 0:
                    memory.delete(
                        collection_name=namespace,
                        ids=[f"chunk_{chunk_hash}"]
                    )
                    ledger.hdel(REDIS_CHUNK_REFCOUNT, chunk_hash)

            # Add new chunks
            documents = []
            ids = []
            metadatas = []

            for chunk in chunks:
                chunk_hash = self._hash(chunk)

                if chunk_hash not in chunks_to_add:
                    continue

                refcount = ledger.hincrby(
                    REDIS_CHUNK_REFCOUNT,
                    chunk_hash,
                    1
                )

                if refcount == 1:
                    documents.append(chunk)
                    ids.append(f"chunk_{chunk_hash}")
                    metadatas.append({
                        "chunk_hash": chunk_hash
                    })

            if documents:
                memory.upsert(
                    collection_name=namespace,
                    documents=documents,
                    ids=ids,
                    metadatas=metadatas
                )

            ledger.delete(url_key)
            if new_chunks:
                ledger.sadd(url_key, *list(new_chunks))

            # 🔥 DISCOVER LINKS WITH SMOOTH BACKPRESSURE
            for link in render_response.hrefs:
                normalized = self._normalize_url(link)

                if ledger.sadd(REDIS_SEEN_URLS, normalized):
                    await self._wait_for_queue_capacity()
                    ledger.lpush(
                        LedgerNamespace.CRAWL_QUEUE,
                        normalized
                    )

            crawling_ledger.mark_visited(
                url,
                content_hash=full_hash
            )

        except Exception as e:
            logger.exception(f"Error processing {url}")
            crawling_ledger.mark_failed(url, str(e))

    # ============================================================
    # RATE LIMITED FETCH
    # ============================================================

    async def _rate_limited_fetch(self, url: str):

        domain = self._get_domain(url)

        async with self.domain_semaphores[domain]:

            now = time.time()
            elapsed = now - self.last_request_time[domain]

            if elapsed < DOMAIN_RATE_LIMIT:
                await asyncio.sleep(DOMAIN_RATE_LIMIT - elapsed)

            self.last_request_time[domain] = time.time()

            for attempt in range(MAX_RETRIES):
                try:
                    return await render_page_deep(url)
                except Exception:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(
                            RETRY_BACKOFF_BASE ** attempt
                        )

        return None


crawler_service = Crawler()

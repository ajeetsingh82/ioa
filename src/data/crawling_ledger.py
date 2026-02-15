import hashlib
import time
from urllib.parse import urlparse
from typing import Optional, Dict

from .ledger import ledger, LedgerNamespace


class CrawlStatus:
    NEW = "new"
    IN_PROGRESS = "in_progress"
    VISITED = "visited"
    FAILED = "failed"


class CrawlingLedger:

    def __init__(self):
        self.ledger = ledger
        self.namespace = LedgerNamespace.CRAWLING.value

    # ------------------------------------------
    # Utilities
    # ------------------------------------------

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip("/")

    @staticmethod
    def _hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def _get_domain(url: str) -> str:
        return urlparse(url).netloc.lower()

    # ------------------------------------------
    # Core Operations
    # ------------------------------------------

    def has_been_crawled(self, url: str, freshness_window: Optional[int] = None) -> bool:
        url = self._normalize_url(url)
        domain = self._get_domain(url)
        field = self._hash_url(url)

        record = self.ledger.hget(self.namespace, domain, field)

        if not record:
            return False

        if freshness_window:
            return (time.time() - record["last_crawled"]) < freshness_window

        return record["status"] == CrawlStatus.VISITED

    def claim_for_crawling(self, url: str, lock_ttl: int = 120) -> bool:
        """
        Atomically claim URL for crawling.
        Prevents duplicate parallel crawls.
        """
        url = self._normalize_url(url)
        lock_key = f"crawl_lock:{self._hash_url(url)}"
        return self.ledger.acquire_lock(lock_key, ttl=lock_ttl)

    def mark_in_progress(self, url: str):
        self._update_status(url, CrawlStatus.IN_PROGRESS)

    def mark_visited(
            self,
            url: str,
            etag: Optional[str] = None,
            content_hash: Optional[str] = None,
    ):
        self._update_status(
            url,
            CrawlStatus.VISITED,
            extra={
                "etag": etag,
                "content_hash": content_hash,
            },
        )

    def mark_failed(self, url: str, error: Optional[str] = None):
        self._update_status(
            url,
            CrawlStatus.FAILED,
            extra={"error": error},
        )

    # ------------------------------------------
    # Internal Update
    # ------------------------------------------

    def _update_status(
            self,
            url: str,
            status: str,
            extra: Optional[Dict] = None,
    ):
        url = self._normalize_url(url)
        domain = self._get_domain(url)
        field = self._hash_url(url)

        record = {
            "url": url,
            "status": status,
            "last_crawled": int(time.time()),
        }

        if extra:
            record.update({k: v for k, v in extra.items() if v is not None})

        self.ledger.hset(self.namespace, domain, field, record)

crawling_ledger = CrawlingLedger()

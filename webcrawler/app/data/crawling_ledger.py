import hashlib
import time
from urllib.parse import urlparse
from typing import Optional, Dict

from .ledger import ledger


class CrawlStatus:
    NEW = "new"
    IN_PROGRESS = "in_progress"
    VISITED = "visited"
    FAILED = "failed"


class CrawlingLedger:

    def __init__(self):
        self.ledger = ledger
        self.namespace = "crawled"

    # =========================================================
    # Utilities
    # =========================================================

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

    def _key(self, url: str) -> str:
        return f"{self.namespace}:{self._hash_url(url)}"

    def _lock_key(self, url: str) -> str:
        return f"crawl_lock:{self._hash_url(url)}"

    # =========================================================
    # Core Queries
    # =========================================================

    def get_record(self, url: str) -> Optional[Dict]:
        url = self._normalize_url(url)
        key = self._key(url)

        record = self.ledger.client.hgetall(key)
        return record if record else None

    def get_content_hash(self, url: str) -> Optional[str]:
        url = self._normalize_url(url)
        key = self._key(url)
        return self.ledger.client.hget(key, "content_hash")

    def get_status(self, url: str) -> Optional[str]:
        url = self._normalize_url(url)
        key = self._key(url)
        return self.ledger.client.hget(key, "status")

    def has_been_crawled(
            self,
            url: str,
            freshness_window: Optional[int] = None
    ) -> bool:
        url = self._normalize_url(url)
        key = self._key(url)

        status = self.ledger.client.hget(key, "status")
        if not status:
            return False

        if freshness_window:
            last_crawled = self.ledger.client.hget(key, "last_crawled")
            if not last_crawled:
                return False
            return (time.time() - float(last_crawled)) < freshness_window

        return status == CrawlStatus.VISITED

    # =========================================================
    # Locking
    # =========================================================

    def claim_for_crawling(self, url: str, lock_ttl: int = 120) -> bool:
        url = self._normalize_url(url)
        return self.ledger.acquire_lock(self._lock_key(url), ttl=lock_ttl)

    def release_lock(self, url: str):
        url = self._normalize_url(url)
        self.ledger.release_lock(self._lock_key(url))

    # =========================================================
    # Status Updates
    # =========================================================

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
                "error": None
            },
        )
        self.release_lock(url)

    def mark_failed(self, url: str, error: Optional[str] = None):
        self._update_status(
            url,
            CrawlStatus.FAILED,
            extra={"error": error},
        )
        self.release_lock(url)

    # =========================================================
    # Internal Write
    # =========================================================

    def _update_status(
            self,
            url: str,
            status: str,
            extra: Optional[Dict] = None,
    ):
        url = self._normalize_url(url)
        key = self._key(url)

        record = {
            "url": url,
            "domain": self._get_domain(url),
            "status": status,
            "last_crawled": str(time.time()),
        }

        if extra:
            record.update({k: v for k, v in extra.items() if v is not None})

        self.ledger.client.hset(key, mapping=record)


crawling_ledger = CrawlingLedger()

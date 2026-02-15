import os
import redis
import json
import logging
from typing import Optional, Any, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class LedgerNamespace(str, Enum):
    CRAWLING = "crawled"
    SESSIONS = "sessions"
    CRAWL_QUEUE = "crawl_queue"


class LedgerError(Exception):
    pass


class Ledger:
    """
    Production-grade Redis DAO (Hash optimized).
    """

    def __init__(
            self,
            host: Optional[str] = None,
            port: Optional[int] = None,
            db: int = 0,
            password: Optional[str] = None,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.db = db
        self.password = password

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            self.client.ping()
        except redis.ConnectionError as e:
            raise LedgerError(f"Redis connection failed: {e}")

    # ------------------------------------------
    # Hash Operations
    # ------------------------------------------

    def hset(
            self,
            namespace: str,
            key: str,
            field: str,
            value: Dict,
    ) -> None:
        try:
            self.client.hset(
                f"{namespace}:{key}",
                field,
                json.dumps(value),
            )
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hget(
            self,
            namespace: str,
            key: str,
            field: str,
    ) -> Optional[Dict]:
        try:
            value = self.client.hget(f"{namespace}:{key}", field)
            return json.loads(value) if value else None
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hexists(self, namespace: str, key: str, field: str) -> bool:
        return self.client.hexists(f"{namespace}:{key}", field)

    def hdel(self, namespace: str, key: str, field: str) -> None:
        self.client.hdel(f"{namespace}:{key}", field)

    # ------------------------------------------
    # List (Queue) Operations
    # ------------------------------------------

    def lpush(self, queue_name: str, *values: Any) -> int:
        """Pushes values onto the left side of a list (queue)."""
        try:
            return self.client.lpush(queue_name, *values)
        except redis.RedisError as e:
            logger.exception(f"Ledger LPUSH failed for {queue_name}")
            raise LedgerError(str(e))

    def brpop(self, queue_names: List[str], timeout: int = 0) -> Optional[tuple]:
        """Blocking right-pop from a list (queue). Waits for an item to be available."""
        try:
            # Returns a tuple (queue_name, value) or None
            return self.client.brpop(queue_names, timeout)
        except redis.RedisError as e:
            logger.exception(f"Ledger BRPOP failed for {queue_names}")
            raise LedgerError(str(e))

    # ------------------------------------------
    # Atomic Lock (SETNX)
    # ------------------------------------------

    def acquire_lock(self, lock_key: str, ttl: int = 60) -> bool:
        """
        Atomic lock using SET NX.
        Prevents duplicate crawling.
        """
        return self.client.set(lock_key, "1", nx=True, ex=ttl)

    def release_lock(self, lock_key: str):
        self.client.delete(lock_key)

    def health_check(self) -> bool:
        try:
            return self.client.ping()
        except Exception:
            return False


ledger = Ledger()

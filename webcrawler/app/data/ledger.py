import os
import redis
import json
import logging
from typing import Optional, Any, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============================================================
# Namespaces
# ============================================================

class LedgerNamespace(str, Enum):
    CRAWLING = "crawled"
    SESSIONS = "sessions"
    CRAWL_QUEUE = "crawl_queue"


class LedgerError(Exception):
    pass


# ============================================================
# Ledger
# ============================================================

class Ledger:
    """
    Production-grade Redis abstraction.

    Supports:
      - Structured namespaced hashes
      - Raw hash operations
      - Sets
      - Lists (queues)
      - Strings
      - Atomic counters
      - Locks
    """

    # ============================================================
    # INIT
    # ============================================================

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

    # ============================================================
    # INTERNAL
    # ============================================================

    def _ns(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    # ============================================================
    # STRUCTURED HASH (Namespaced)
    # ============================================================

    def hset(
            self,
            namespace: str,
            key: str,
            field: str,
            value: Any,
            json_encode: bool = True,
    ):
        try:
            redis_key = self._ns(namespace, key)
            if json_encode:
                value = json.dumps(value)
            self.client.hset(redis_key, field, value)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hget(
            self,
            namespace: str,
            key: str,
            field: str,
            json_decode: bool = True,
    ) -> Optional[Any]:
        try:
            redis_key = self._ns(namespace, key)
            value = self.client.hget(redis_key, field)

            if value is None:
                return None

            if json_decode:
                return json.loads(value)

            return value
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hgetall(
            self,
            namespace: str,
            key: str,
            json_decode: bool = True,
    ) -> Dict[str, Any]:
        try:
            redis_key = self._ns(namespace, key)
            data = self.client.hgetall(redis_key)

            if json_decode:
                return {
                    k: json.loads(v)
                    for k, v in data.items()
                }

            return data
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hexists(self, namespace: str, key: str, field: str) -> bool:
        return self.client.hexists(self._ns(namespace, key), field)

    def hdel(self, namespace: str, key: str, *fields: str):
        self.client.hdel(self._ns(namespace, key), *fields)

    # ============================================================
    # RAW HASH OPERATIONS (For refcounting etc.)
    # ============================================================

    def hincrby(self, key: str, field: str, amount: int) -> int:
        try:
            return self.client.hincrby(key, field, amount)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def hdel_raw(self, key: str, *fields: str):
        try:
            return self.client.hdel(key, *fields)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    # ============================================================
    # SET OPERATIONS
    # ============================================================

    def sadd(self, key: str, *values: Any) -> int:
        try:
            return self.client.sadd(key, *values)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def sismember(self, key: str, value: Any) -> bool:
        try:
            return self.client.sismember(key, value)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def smembers(self, key: str) -> set:
        try:
            return self.client.smembers(key)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def srem(self, key: str, *values: Any) -> int:
        try:
            return self.client.srem(key, *values)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    # ============================================================
    # LIST (QUEUE)
    # ============================================================

    def lpush(self, key: str, *values: Any) -> int:
        try:
            return self.client.lpush(key, *values)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def brpop(self, keys: List[str], timeout: int = 0):
        try:
            return self.client.brpop(keys, timeout)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def llen(self, key: str) -> int:
        return self.client.llen(key)

    # ============================================================
    # STRING
    # ============================================================

    def set(self, key: str, value: Any, nx: bool = False, ex: int = None):
        try:
            return self.client.set(key, value, nx=nx, ex=ex)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def get(self, key: str) -> Optional[str]:
        try:
            return self.client.get(key)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    # ============================================================
    # GENERAL
    # ============================================================

    def delete(self, *keys: str) -> int:
        try:
            return self.client.delete(*keys)
        except redis.RedisError as e:
            raise LedgerError(str(e))

    def exists(self, key: str) -> bool:
        return self.client.exists(key) > 0

    # ============================================================
    # LOCKS
    # ============================================================

    def acquire_lock(self, lock_key: str, ttl: int = 60) -> bool:
        return self.set(lock_key, "1", nx=True, ex=ttl)

    def release_lock(self, lock_key: str):
        self.delete(lock_key)

    # ============================================================
    # HEALTH
    # ============================================================

    def health_check(self) -> bool:
        try:
            return self.client.ping()
        except Exception:
            return False


ledger = Ledger()

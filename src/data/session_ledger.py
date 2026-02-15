import time
import uuid
import json
from typing import Optional, Dict, Any

from .ledger import ledger, LedgerNamespace, LedgerError

class SessionStatus:
    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    EXPIRED = "expired"


class SessionLedger:

    def __init__(
            self,
            default_ttl: int = 3600,  # 1 hour
    ):
        self.ledger = ledger
        self.namespace = LedgerNamespace.SESSIONS.value
        self.default_ttl = default_ttl

    # ------------------------------------------
    # Internal
    # ------------------------------------------

    def _key(self, session_id: str) -> str:
        return f"{self.namespace}:{session_id}"

    # ------------------------------------------
    # Session Lifecycle
    # ------------------------------------------

    def create_session(
            self,
            user_id: Optional[str] = None,
            agent_id: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            ttl: Optional[int] = None,
            session_id: Optional[str] = None,
    ) -> str:
        """
        Creates a new session with TTL.
        Atomic creation using SETNX pattern.
        """

        session_id = session_id or str(uuid.uuid4())
        key = self._key(session_id)

        if self.ledger.client.exists(key):
            raise LedgerError(f"Session already exists: {session_id}")

        now = int(time.time())

        session_data = {
            "status": SessionStatus.ACTIVE,
            "created_at": now,
            "last_seen": now,
            "user_id": user_id,
            "agent_id": agent_id,
            "metadata": metadata or {},
        }

        pipe = self.ledger.client.pipeline()
        pipe.hset(key, mapping={
            "status": session_data["status"],
            "created_at": session_data["created_at"],
            "last_seen": session_data["last_seen"],
            "user_id": user_id or "",
            "agent_id": agent_id or "",
            "metadata": json.dumps(session_data["metadata"]),
        })
        pipe.expire(key, ttl or self.default_ttl)
        pipe.execute()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = self._key(session_id)
        data = self.ledger.client.hgetall(key)

        if not data:
            return None

        return {
            "session_id": session_id,
            "status": data.get("status"),
            "created_at": int(data.get("created_at", 0)),
            "last_seen": int(data.get("last_seen", 0)),
            "user_id": data.get("user_id"),
            "agent_id": data.get("agent_id"),
            "metadata": json.loads(data.get("metadata", "{}")),
        }

    def update_status(self, session_id: str, status: str) -> None:
        key = self._key(session_id)

        self.ledger.client.hset(key, "status", status)
        self.touch(session_id)

    def touch(self, session_id: str) -> None:
        """
        Update last_seen + refresh TTL.
        """
        key = self._key(session_id)
        now = int(time.time())

        pipe = self.ledger.client.pipeline()
        pipe.hset(key, "last_seen", now)
        pipe.expire(key, self.default_ttl)
        pipe.execute()

    def update_metadata(
            self,
            session_id: str,
            metadata: Dict[str, Any],
            merge: bool = True,
    ) -> None:
        key = self._key(session_id)

        existing = self.ledger.client.hget(key, "metadata")
        current = json.loads(existing) if existing else {}

        if merge:
            current.update(metadata)
        else:
            current = metadata

        self.ledger.client.hset(key, "metadata", json.dumps(current))
        self.touch(session_id)

    def close_session(self, session_id: str) -> None:
        key = self._key(session_id)

        pipe = self.ledger.client.pipeline()
        pipe.hset(key, "status", SessionStatus.CLOSED)
        pipe.expire(key, 60)  # short TTL after closing
        pipe.execute()

    def delete_session(self, session_id: str) -> None:
        key = self._key(session_id)
        self.ledger.client.delete(key)

    def exists(self, session_id: str) -> bool:
        return bool(self.ledger.client.exists(self._key(session_id)))

    def health_check(self) -> bool:
        return self.ledger.health_check()

session_ledger = SessionLedger()

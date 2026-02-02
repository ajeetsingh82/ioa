import time
import uuid
from typing import List, Dict, Optional

# In-memory database for agents, keyed by agent ID
_agents: Dict[str, Dict] = {}

class Registry:
    """
    A service to track all online agents using a Hierarchical Namespace.
    """

    def register(
        self,
        name: str,
        agent_type: str,
        address: str,
        domain: str,
        capabilities: List[str],
    ) -> Dict:
        """
        Registers a new agent. Name should be hierarchical (e.g., 'hub.student').
        """
        existing_agent_id = self.find_by_exact_name(name)
        agent_id = existing_agent_id if existing_agent_id else str(uuid.uuid4())

        agent_record = {
            "id": agent_id,
            "name": name, # Hierarchical name: hub.student, hub.teacher
            "type": agent_type,
            "address": address,
            "context": {
                "domain": domain,
                "capabilities": capabilities,
            },
            "last_seen": time.time(),
        }
        _agents[agent_id] = agent_record
        print(f"[Registry] Registered: {name} ({agent_id})")
        return agent_record

    def get(self, agent_id: str) -> Optional[Dict]:
        return _agents.get(agent_id)

    def find_by_exact_name(self, name: str) -> Optional[str]:
        for agent_id, record in _agents.items():
            if record["name"] == name:
                return agent_id
        return None

    def find_subnet(self, namespace: str) -> List[Dict]:
        """
        Returns all agents that belong to the given namespace (subnet).
        Example: 'hub' returns ['hub.student', 'hub.teacher']
        """
        subnet_agents = []
        for record in _agents.values():
            # Check if the agent's name starts with the namespace
            # We add a dot to ensure we match full segments (e.g., 'hub.' matches 'hub.student' but not 'hubber')
            # Or if it's an exact match
            if record["name"] == namespace or record["name"].startswith(f"{namespace}."):
                subnet_agents.append(record)
        return subnet_agents

    def list_all(self) -> List[Dict]:
        return list(_agents.values())

    def heartbeat(self, agent_id: str) -> bool:
        if agent_id in _agents:
            _agents[agent_id]["last_seen"] = time.time()
            return True
        return False

    def prune_stale(self, stale_threshold_seconds: int = 300):
        current_time = time.time()
        stale_ids = [
            aid for aid, r in _agents.items()
            if (current_time - r.get("last_seen", 0)) > stale_threshold_seconds
        ]
        for aid in stale_ids:
            print(f"[Registry] Pruning: {_agents[aid]['name']}")
            del _agents[aid]

registry_service = Registry()
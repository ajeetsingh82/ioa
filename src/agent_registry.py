# This module acts as the "Central Ledger" for all agents in the network.
import logging
import random
from typing import Dict, List, Optional

# Configure logger for the registry
logger = logging.getLogger("AgentRegistry")

class AgentRegistry:
    """
    Manages the registration of all specialized agents.
    No longer manages leasing/locking; agents manage their own queues.
    """
    def __init__(self):
        # {agent_type: [agent_address1, agent_address2, ...]}
        self._agents: Dict[str, List[str]] = {}

    def register(self, agent_type: str, address: str):
        """Adds a new agent to the registry."""
        if agent_type not in self._agents:
            self._agents[agent_type] = []
        
        if address not in self._agents[agent_type]:
            self._agents[agent_type].append(address)
            logger.debug(f"Registered {agent_type} agent: {address}")

    def get_agent(self, agent_type: str) -> Optional[str]:
        """Returns the address of an agent of a specific type."""
        if agent_type in self._agents and self._agents[agent_type]:
            # Simple load balancing: Random choice
            # (Round-robin would require state, random is good enough for now)
            return random.choice(self._agents[agent_type])
        logger.warning(f"No {agent_type} agents available.")
        return None

    def get_agent_type(self, address: str) -> Optional[str]:
        """Retrieves the type of an agent given its address."""
        for agent_type, addresses in self._agents.items():
            if address in addresses:
                return agent_type
        return None

# Instantiate a single registry to be used across the application
agent_registry = AgentRegistry()

# This module acts as the "Central Ledger" for all agents in the network.
import logging
from typing import Dict, List, Optional

# Configure logger for the registry
logger = logging.getLogger("AgentRegistry")

class AgentRegistry:
    """
    Manages the registration, status, and leasing of all specialized agents.
    """
    def __init__(self):
        # {agent_type: {agent_address: status}}
        # e.g., {"scout": {"agent1...": "idle", "agent2...": "busy"}}
        self._agents: Dict[str, Dict[str, str]] = {}

    def register(self, agent_type: str, address: str):
        """Adds a new agent to the registry, defaulting to 'idle'."""
        # agent_type = agent_type.lower() # Removed lowercasing
        if agent_type not in self._agents:
            self._agents[agent_type] = {}
        self._agents[agent_type][address] = "idle"
        logger.debug(f"Registered {agent_type} agent: {address}")

    def lease_agent(self, agent_type: str) -> Optional[str]:
        """Finds an idle agent of a specific type, marks it as busy, and returns its address."""
        # agent_type = agent_type.lower() # Removed lowercasing
        if agent_type in self._agents:
            for address, status in self._agents[agent_type].items():
                if status == "idle":
                    self._agents[agent_type][address] = "busy"
                    logger.debug(f"Leased {agent_type} agent: {address}")
                    return address
        logger.warning(f"No idle {agent_type} agents available to lease.")
        return None

    def release_agent(self, agent_type: str, address: str):
        """Marks a leased agent as idle, returning it to the available pool."""
        # agent_type = agent_type.lower() # Removed lowercasing
        if agent_type in self._agents and address in self._agents[agent_type]:
            self._agents[agent_type][address] = "idle"
            logger.debug(f"Released {agent_type} agent: {address}")

    def get_agent_type(self, address: str) -> Optional[str]:
        """Retrieves the type of an agent given its address."""
        for agent_type, agents in self._agents.items():
            if address in agents:
                return agent_type
        return None

# Instantiate a single registry to be used across the application
agent_registry = AgentRegistry()

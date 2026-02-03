# This module defines the Base for all cognitive agents in the system.
import os
import requests
from uagents import Agent, Context
from ..model.models import AgentRegistration

# Centralized LLM configuration
LLM_URL = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")

class BaseAgent(Agent):
    """
    The BaseAgent provides core cognitive abilities and autonomous registration.
    """
    def __init__(self, name: str, seed: str, port: int = 0, conductor_address: str = None):
        super().__init__(name=name, seed=seed, port=port)
        self._agent_type = "base"
        self._conductor_address = conductor_address
        self.on_event("startup")(self.register_on_startup)

    async def register_on_startup(self, ctx: Context):
        """All agents inheriting from BaseAgent will register themselves on startup."""
        if self._conductor_address:
            self._logger.info(f"Registering {self._agent_type} agent with Conductor.")
            await ctx.send(self._conductor_address, AgentRegistration(agent_type=self._agent_type))

    async def think(self, context: str, goal: str) -> str:
        """The core cognitive loop for any agent that inherits this class."""
        prompt = f"### CONTEXT:\n{context}\n\n### TASK:\n{goal}\n\n### RESPONSE:"
        try:
            self._logger.info(f"Agent {self.name} is thinking...")
            response = requests.post(
                LLM_URL,
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            self._logger.info(f"Agent {self.name} finished thinking.")
            return response.json().get('response', "").strip()
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Error connecting to LLM for agent {self.name}: {e}")
            return f"Error: Could not connect to the language model."
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in think() for agent {self.name}: {e}")
            return f"Error: An unexpected error occurred."

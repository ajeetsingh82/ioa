# This module defines the Base for all cognitive agents in the system.
import os
import httpx
from uagents import Agent, Context
from ..model.models import AgentRegistration
from typing import Optional

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
        self._http_client: Optional[httpx.AsyncClient] = None
        
        self.on_event("startup")(self.initialize_client)
        self.on_event("shutdown")(self.close_client)
        self.on_event("startup")(self.register_on_startup)

    async def initialize_client(self, ctx: Context):
        """Initializes the httpx.AsyncClient."""
        self._http_client = httpx.AsyncClient(timeout=120.0)
        ctx.logger.debug(f"HTTP client initialized for {self.name}.")

    async def close_client(self, ctx: Context):
        """Closes the httpx.AsyncClient."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            ctx.logger.debug(f"HTTP client closed for {self.name}.")

    async def register_on_startup(self, ctx: Context):
        """All agents inheriting from BaseAgent will register themselves on startup."""
        if self._conductor_address:
            # This is a high-level event, so INFO is appropriate here.
            self._logger.info(f"Registering {self._agent_type} agent '{self.name}' with Conductor.")
            await ctx.send(self._conductor_address, AgentRegistration(agent_type=self._agent_type))

    async def think(self, context: str, goal: str) -> str:
        """The core cognitive loop for any agent that inherits this class."""
        prompt = f"### CONTEXT:\n{context}\n\n### TASK:\n{goal}\n\n### RESPONSE:"
        if not self._http_client:
            self._logger.error("HTTP client not initialized.")
            return "Error: HTTP client not available."
        try:
            self._logger.info(f"Agent {self.name} is thinking...")
            response = await self._http_client.post(
                LLM_URL,
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            self._logger.info(f"Agent {self.name} finished thinking.")
            return response.json().get('response', "").strip()
        except httpx.HTTPStatusError as e:
            self._logger.error(f"LLM request for agent {self.name} failed with status {e.response.status_code}: {e.response.text}")
            return f"Error: LLM request failed with status code {e.response.status_code}."
        except httpx.RequestError as e:
            self._logger.error(f"Error connecting to LLM for agent {self.name}: {e}")
            return f"Error: Could not connect to the language model."
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in think() for agent {self.name}: {e}", exc_info=True)
            return f"Error: An unexpected error occurred."

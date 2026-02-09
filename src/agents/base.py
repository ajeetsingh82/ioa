import os
import httpx
import asyncio
from uagents import Agent, Context
from typing import Optional, Callable, Any

from ..model.models import AgentRegistration
from ..agent_registry import agent_registry
from ..model.agent_model_registry import model_registry

AGENT_TYPE_BASE = "BASE"

class BaseAgent(Agent):
    """
    The BaseAgent provides core cognitive abilities and autonomous registration.
    """
    def __init__(self, name: str, seed: str, port: int = 0, conductor_address: str = None):
        super().__init__(name=name, seed=seed, port=port)
        self.type = AGENT_TYPE_BASE
        self._conductor_address = conductor_address
        self._http_client: Optional[httpx.AsyncClient] = None
        
        self.on_event("startup")(self.initialize_client)
        self.on_event("shutdown")(self.close_client)
        self.on_event("startup")(self.register_on_startup)

    async def initialize_client(self, ctx: Context):
        self._http_client = httpx.AsyncClient(timeout=300.0)
        ctx.logger.debug(f"HTTP client initialized for {self.name} with a 300s timeout.")

    async def close_client(self, ctx: Context):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            ctx.logger.debug(f"HTTP client closed for {self.name}.")

    async def register_on_startup(self, ctx: Context):
        agent_type_str = self.type.value if hasattr(self.type, 'value') else str(self.type)
        agent_registry.register(agent_type_str, self.address)
        self._logger.info(f"Registered {agent_type_str} agent '{self.name}' with Registry.")
        
        if self._conductor_address:
            await ctx.send(self._conductor_address, AgentRegistration(agent_type=agent_type_str))

    async def think(self, context: str, goal: str) -> str:
        if not self._http_client:
            self._logger.error("HTTP client not initialized.")
            return "Error: HTTP client not available."

        config = model_registry.get_agent_model_config(self.type)
        
        if config.get("api_type") != "chat":
            error_msg = f"Agent {self.name} of type {self.type.value} is not configured for chat generation."
            self._logger.error(error_msg)
            return f"Error: {error_msg}"

        system_prompt = f"CONTEXT:\n{context}\n\nTASK:\n{goal}"
        
        payload = {
            "model": config["model"],
            "messages": [{"role": "system", "content": system_prompt}],
            "stream": False,
            "options": {
                "temperature": config.get("temperature", 0.3),
                "num_predict": config.get("max_tokens", 1024)
            }
        }
        
        try:
            self._logger.debug(f"Agent {self.name} thinking with model {config['model']}...")
            response = await self._http_client.post(config["endpoint"], json=payload)
            response.raise_for_status()
            self._logger.debug(f"Agent {self.name} finished thinking.")
            
            response_data = response.json()
            content = response_data.get('message', {}).get('content', '')
            return content.replace("<|start_header_id|>assistant<|end_header_id|>", "").strip()

        except httpx.RequestError as e:
            self._logger.error(f"Error connecting to LLM for agent {self.name}: {e}")
            return f"Error: Could not connect to the language model at {config['endpoint']}."
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in think() for agent {self.name}: {e}", exc_info=True)
            return "Error: An unexpected error occurred."

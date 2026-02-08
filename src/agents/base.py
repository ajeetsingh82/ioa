# This module defines the Base for all cognitive agents in the system.
import os
import httpx
import asyncio
from uagents import Agent, Context
from ..model.models import AgentRegistration
from ..agent_registry import agent_registry
from typing import Optional, Callable, Any

# Centralized LLM configuration
LLM_URL = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")

AGENT_TYPE_BASE = "BASE"

class BaseAgent(Agent):
    """
    The BaseAgent provides core cognitive abilities, autonomous registration,
    and a request queue for processing tasks sequentially.
    """
    def __init__(self, name: str, seed: str, port: int = 0, conductor_address: str = None):
        super().__init__(name=name, seed=seed, port=port)
        self.type = AGENT_TYPE_BASE # Default type
        self._conductor_address = conductor_address
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Request Queue for sequential processing
        self.request_queue = asyncio.Queue()
        
        self.on_event("startup")(self.initialize_client)
        self.on_event("shutdown")(self.close_client)
        self.on_event("startup")(self.register_on_startup)
        self.on_interval(period=0.1)(self.process_request_queue)

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
        """Registers the agent directly with the central registry."""
        # Direct registration (preferred for single-process/bureau setup)
        agent_registry.register(self.type, self.address)
        self._logger.info(f"Registered {self.type} agent '{self.name}' with Registry.")

        # Legacy/Distributed registration via message
        if self._conductor_address:
            self._logger.info(f"Sending registration message to Conductor at {self._conductor_address}")
            await ctx.send(self._conductor_address, AgentRegistration(agent_type=self.type))

    async def process_request_queue(self, ctx: Context):
        """Drains the request queue and executes tasks."""
        while not self.request_queue.empty():
            # Retrieve the task
            original_ctx, sender, msg, func = await self.request_queue.get()
            try:
                # Execute the task using the original context
                await func(original_ctx, sender, msg)
            except Exception as e:
                ctx.logger.error(f"Error processing request in queue: {e}")
            finally:
                self.request_queue.task_done()

    async def enqueue_request(self, ctx: Context, sender: str, msg: Any, func: Callable):
        """Enqueues a request to be processed by the agent's main loop."""
        await self.request_queue.put((ctx, sender, msg, func))
        ctx.logger.debug(f"Enqueued request from {sender}. Queue size: {self.request_queue.qsize()}")

    def queued_handler(self, func: Callable):
        """
        Returns an async handler that enqueues the request instead of processing it immediately.
        Use this to wrap your processing logic when registering handlers.
        """
        async def wrapper(ctx: Context, sender: str, msg: Any):
            await self.enqueue_request(ctx, sender, msg, func)
        return wrapper

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

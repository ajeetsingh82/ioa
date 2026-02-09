import os
import httpx
from queue import Queue
from uagents import Agent, Context

from ..utils.utils import clean_gateway_response
from ..model.models import Response, UserQuery
from ..model.agent_types import AgentType
from ..config.store import agent_config_store
from ..agent_registry import agent_registry
from ..model.agent_model_registry import model_registry

class GatewayAgent(Agent):
    """
    Standalone Gateway Agent that handles user queries and system responses.
    It uses the OllamaModelRegistry to format its final response.
    """
    def __init__(self, name: str, seed: str):
        super().__init__(name=name, seed=seed)
        self.type = AgentType.SPEAKER
        self.query_queue = Queue()
        self.response_queue = []
        self._queries = {}
        self._http_client = None
        
        speaker_config = agent_config_store.get_config(self.type.value)
        if not speaker_config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.speaker_prompt = speaker_config.get_prompt('speaker')
        self.failure_prompt = speaker_config.get_prompt('failure')
        if not self.speaker_prompt or not self.failure_prompt:
            raise ValueError(f"Required prompts not found for agent type '{self.type.value}'.")

        self.on_event("startup")(self.initialize_client)
        self.on_event("shutdown")(self.close_client)
        self.on_interval(period=0.5)(self.process_query_queue)
        self.on_interval(period=0.5)(self.process_response_queue)
        self.on_message(model=Response)(self.handle_response)

    async def initialize_client(self, ctx: Context):
        self._http_client = httpx.AsyncClient(timeout=120.0)
        ctx.logger.debug(f"HTTP client initialized for {self.name}.")

    async def close_client(self, ctx: Context):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            ctx.logger.debug(f"HTTP client closed for {self.name}.")

    def remember_query(self, request_id: str, query: str):
        self._queries[request_id] = query

    async def process_query_queue(self, ctx: Context):
        while not self.query_queue.empty():
            msg = self.query_queue.get()
            if isinstance(msg, UserQuery):
                self.remember_query(msg.request_id, msg.text)
                conductor_address = agent_registry.get_agent("conductor")
                if conductor_address:
                    await ctx.send(conductor_address, msg)
                else:
                    ctx.logger.error("Conductor address not found. Is it running?")

    async def handle_response(self, ctx: Context, sender: str, msg: Response):
        original_query = self._queries.get(msg.request_id, "your question")
        response_job = {
            "request_id": msg.request_id,
            "status": "success",
            "synthesized_data": msg.content,
            "original_query": original_query,
            "type": msg.type
        }
        self.response_queue.append(response_job)
        ctx.logger.info(f"Pushed response for request {msg.request_id} to response queue.")
        if msg.request_id in self._queries and msg.type == -1:
            del self._queries[msg.request_id]

    async def process_response_queue(self, ctx: Context):
        if not self.response_queue:
            return
        job = self.response_queue.pop(0)
        ctx.logger.info(f"Processing job from response queue for request {job['request_id']}")

        final_text = ""
        if job["synthesized_data"]:
            if job["status"] == "success":
                prompt = self.speaker_prompt.format(query=job["original_query"], data=job["synthesized_data"])
            else:
                prompt = self.failure_prompt.format(query=job["original_query"])
            final_text = await self.think(context="", goal=prompt)

        chat_server_url = os.getenv("CHAT_SERVER_URL", "http://webapp-ui:8080/api/result")
        ctx.logger.info(f"Formatted final answer for request {job['request_id']}. Sending to chat server at {chat_server_url}")
        final_text = clean_gateway_response(final_text)
        try:
            async with httpx.AsyncClient() as client:
                await client.post(chat_server_url, json={
                    "text": final_text, "request_id": job["request_id"], "type": job["type"]
                })
        except httpx.RequestError as e:
            ctx.logger.error(f"Failed to send result to chat server: {e}")

    async def think(self, context: str, goal: str) -> str:
        """The cognitive loop for the Gateway, now compatible with Ollama's /api/chat."""
        if not self._http_client:
            self._logger.error("HTTP client not initialized.")
            return "Error: HTTP client not available."

        config = model_registry.get_agent_model_config(self.type)
        
        if config.get("api_type") != "chat":
            return f"Error: Agent {self.name} is not configured for chat generation."

        system_prompt = f"CONTEXT:\n{context}\n\nTASK:\n{goal}"

        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": system_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": config.get("temperature", 0.2),
                "num_predict": config.get("max_tokens", 1024)
            }
        }
        
        try:
            self._logger.debug(f"Gateway thinking with model {config['model']}...")
            response = await self._http_client.post(config["endpoint"], json=payload)
            response.raise_for_status()
            self._logger.debug("Gateway finished thinking.")
            
            response_data = response.json()
            return response_data.get('message', {}).get('content', '').strip()

        except Exception as e:
            self._logger.error(f"An unexpected error occurred in Gateway think(): {e}", exc_info=True)
            return "Error: An unexpected error occurred during final response generation."

gateway = GatewayAgent(name="gateway", seed="gateway_seed")

import os
import httpx
from queue import Queue
from uagents import Agent, Context
from ..model.models import Response, UserQuery
from ..config.store import agent_config_store
from ..agent_registry import agent_registry

# Centralized LLM configuration (duplicated from BaseAgent for standalone Gateway)
LLM_URL = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")

AGENT_TYPE_USER = "speaker"

class GatewayAgent(Agent):
    """
    Standalone Gateway Agent that handles user queries and system responses.
    It does not inherit from BaseAgent and manages its own lifecycle.
    """
    def __init__(self, name: str, seed: str):
        super().__init__(name=name, seed=seed)
        self.type = AGENT_TYPE_USER
        self.query_queue = Queue()
        self.response_queue = [] # Using list as a queue (FIFO)
        self._queries = {} # Store original queries by request_id
        self._http_client = None
        
        # Load configuration from the central store for the 'speaker' role
        speaker_config = agent_config_store.get_config(self.type)
        if not speaker_config:
            raise ValueError("Configuration for agent type 'SPEAKER' not found.")
        self.speaker_prompt = speaker_config.get_prompt('speaker')
        self.failure_prompt = speaker_config.get_prompt('failure')
        if not self.speaker_prompt or not self.failure_prompt:
            raise ValueError("Required prompts ('default', 'failure') not found for agent type 'speaker'.")

        # Register handlers
        self.on_event("startup")(self.initialize_client)
        self.on_event("shutdown")(self.close_client)
        self.on_interval(period=0.5)(self.process_query_queue)
        self.on_interval(period=0.5)(self.process_response_queue)
        self.on_message(model=Response)(self.handle_response)

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

    def remember_query(self, request_id: str, query: str):
        """Stores the original user query for context."""
        self._queries[request_id] = query

    async def process_query_queue(self, ctx: Context):
        """Reads user queries from the HTTP queue and forwards them to the Conductor."""
        while not self.query_queue.empty():
            msg = self.query_queue.get()
            # Accept UserQuery
            if isinstance(msg, UserQuery):
                self.remember_query(msg.request_id, msg.text)
                
                # Dynamically find the conductor
                conductor_address = agent_registry.get_agent("conductor")
                
                if conductor_address:
                    # Forward as UserQuery
                    await ctx.send(conductor_address, msg)
                else:
                    ctx.logger.error("Conductor address not found in registry. Is the Conductor agent running?")
            else:
                ctx.logger.warning(f"Gateway received unknown message type from queue: {type(msg)}")

    async def handle_response(self, ctx: Context, sender: str, msg: Response):
        """Receives the final response from the Conductor and pushes it to the response queue."""
        original_query = self._queries.get(msg.request_id, "your question")
        
        # Package the job for the response queue
        response_job = {
            "request_id": msg.request_id,
            "status": "success", # Assumed success
            "synthesized_data": msg.content,
            "original_query": original_query,
            "type": msg.type # Pass the type (completion/heartbeat)
        }
        self.response_queue.append(response_job)
        ctx.logger.info(f"Pushed response for request {msg.request_id} to response queue. Type: {msg.type}")

        # Clean up the stored query now that we have what we need
        if msg.request_id in self._queries and msg.type == -1:
            del self._queries[msg.request_id]

    async def process_response_queue(self, ctx: Context):
        """Processes the response queue to format and send the final response to the user."""
        if not self.response_queue:
            return

        job = self.response_queue.pop(0) # FIFO processing
        ctx.logger.info(f"Processing job from response queue for request {job['request_id']}")

        # Only format if there is content. If it's just a heartbeat (type 0) with no content, skip formatting.
        final_text = ""
        if job["synthesized_data"]:
            if job["status"] == "success":
                prompt = self.speaker_prompt.format(query=job["original_query"], data=job["synthesized_data"])
            else:
                prompt = self.failure_prompt.format(query=job["original_query"])
                
            final_text = await self.think(context="", goal=prompt)
            
            # STRICT VALIDATION: Reject JSON or Code Fences
            stripped_text = final_text.strip()
            if stripped_text.startswith("```") or stripped_text.startswith("{") or stripped_text.startswith("["):
                ctx.logger.warning(f"Gateway received malformed output (JSON/Code Fence detected). Retrying with strict instruction.")
                retry_prompt = prompt + "\n\nSYSTEM ALERT: PREVIOUS OUTPUT WAS REJECTED. DO NOT USE CODE FENCES. DO NOT OUTPUT JSON. RETURN ONLY RAW MARKDOWN."
                final_text = await self.think(context="", goal=retry_prompt)
                
                stripped_text = final_text.strip()
                if stripped_text.startswith("```") or stripped_text.startswith("{") or stripped_text.startswith("["):
                     ctx.logger.error("Gateway failed to generate valid Markdown after retry.")
                     final_text = "I apologize, but I am having trouble formatting the answer correctly. Please try again."

        chat_server_url = os.getenv("CHAT_SERVER_URL", "http://localhost:8080/api/result")
        
        ctx.logger.info(f"Formatted final answer for request {job['request_id']}. Sending to chat server at {chat_server_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(chat_server_url, json={
                    "text": final_text,
                    "request_id": job["request_id"],
                    "type": job["type"]
                })
        except httpx.RequestError as e:
            ctx.logger.error(f"Failed to send result to chat server: {e}")
            ctx.logger.error(f"response for request {job['request_id']}:\n{final_text}")

    async def think(self, context: str, goal: str) -> str:
        """
        The core cognitive loop for the Gateway agent.
        Since Gateway is standalone, it implements its own LLM access logic.
        """
        prompt = f"### CONTEXT:\n{context}\n\n### TASK:\n{goal}\n\n### RESPONSE:"
        if not self._http_client:
            self._logger.error("HTTP client not initialized.")
            return "Error: HTTP client not available."
        try:
            self._logger.info(f"Gateway is thinking...")
            response = await self._http_client.post(
                LLM_URL,
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            self._logger.info(f"Gateway finished thinking.")
            return response.json().get('response', "").strip()
        except httpx.HTTPStatusError as e:
            self._logger.error(f"LLM request for Gateway failed with status {e.response.status_code}: {e.response.text}")
            return f"Error: LLM request failed with status code {e.response.status_code}."
        except httpx.RequestError as e:
            self._logger.error(f"Error connecting to LLM for Gateway: {e}")
            return f"Error: Could not connect to the language model."
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in think() for Gateway: {e}", exc_info=True)
            return f"Error: An unexpected error occurred."

# Instantiate the gateway agent globally so it can be imported
gateway = GatewayAgent(name="gateway", seed="gateway_seed")

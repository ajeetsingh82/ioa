import os
import httpx
from queue import Queue
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, UserQuery
from ..config.store import agent_config_store

AGENT_TYPE_USER = "SPEAKER"

class GatewayAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_USER
        self.thought_queue = Queue()
        self.cognition_stack = []
        self.strategist_address = None
        self._queries = {} # Store original queries by request_id
        
        # Load configuration from the central store for the 'speaker' role
        speaker_config = agent_config_store.get_config(self.type)
        if not speaker_config:
            raise ValueError("Configuration for agent type 'SPEAKER' not found.")
        self.speaker_prompt = speaker_config.get_prompt('speaker')
        self.failure_prompt = speaker_config.get_prompt('failure')
        if not self.speaker_prompt or not self.failure_prompt:
            raise ValueError("Required prompts ('default', 'failure') not found for agent type 'speaker'.")

        # Register handlers
        self.on_interval(period=0.5)(self.process_queue)
        self.on_interval(period=0.5)(self.process_cognition_stack)
        self.on_message(model=Thought)(self.handle_thought)

    def remember_query(self, request_id: str, query: str):
        """Stores the original user query for context."""
        self._queries[request_id] = query

    async def process_queue(self, ctx: Context):
        """Reads user queries from the HTTP queue and forwards them."""
        while not self.thought_queue.empty():
            msg = self.thought_queue.get()
            if isinstance(msg, UserQuery):
                self.remember_query(msg.request_id, msg.text)
                
                if self.strategist_address:
                    await ctx.send(self.strategist_address, msg)
                else:
                    ctx.logger.error("Strategist address not configured")
            else:
                ctx.logger.warning(f"Gateway received unknown message type from queue: {type(msg)}")

    async def handle_thought(self, ctx: Context, sender: str, msg: Thought):
        """Receives the final thought from the Architect and pushes it to the cognition stack."""
        if msg.type != "RESPONSE":
            ctx.logger.warning(f"Gateway received unexpected Thought type: {msg.type}")
            return

        original_query = self._queries.get(msg.request_id, "your question")
        
        # Package the job for the cognition stack
        response_job = {
            "request_id": msg.request_id,
            "status": msg.metadata.get("status", "failure"),
            "synthesized_data": msg.content,
            "original_query": original_query
        }
        self.cognition_stack.append(response_job)
        ctx.logger.info(f"Pushed response for request {msg.request_id} to cognition stack.")

        # Clean up the stored query now that we have what we need
        if msg.request_id in self._queries:
            del self._queries[msg.request_id]

    async def process_cognition_stack(self, ctx: Context):
        """Processes the cognition stack to format and send the final response to the user."""
        if not self.cognition_stack:
            return

        job = self.cognition_stack.pop(0) # FIFO processing
        ctx.logger.info(f"Processing job from cognition stack for request {job['request_id']}")

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

        chat_server_url = os.getenv("CHAT_SERVER_URL", "http://127.0.0.1:8080/api/result")
        
        ctx.logger.info(f"Formatted final answer for request {job['request_id']}. Sending to chat server at {chat_server_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(chat_server_url, json={
                    "text": final_text,
                    "request_id": job["request_id"]
                })
        except httpx.RequestError as e:
            ctx.logger.error(f"Failed to send result to chat server: {e}")
            ctx.logger.error(f"response for request {job['request_id']}:\n{final_text}")

# Instantiate the gateway agent globally so it can be imported
gateway = GatewayAgent(name="gateway", seed="gateway_seed")

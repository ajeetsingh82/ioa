# The User Proxy Agent: The "Speaker" and "Human Liaison"
import os
import httpx
from uagents import Context
from .base import BaseAgent
from ..model.models import ArchitectResponse

class UserProxy(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "user_proxy"
        self._queries = {} # Store original queries by request_id
        self.on_message(model=ArchitectResponse)(self.handle_architect_response)

    def remember_query(self, request_id: str, query: str):
        """Stores the original user query for context."""
        self._queries[request_id] = query

    async def handle_architect_response(self, ctx: Context, sender: str, msg: ArchitectResponse):
        """
        Receives the structured data from the Architect, formats it,
        and POSTs the final result to the chat server.
        """
        from ..prompt.prompt import SPEAKER_PROMPT, FAILURE_PROMPT
        original_query = self._queries.get(msg.request_id, "your question")

        if msg.status == "success":
            prompt = SPEAKER_PROMPT.format(query=original_query, data=msg.synthesized_data)
        else:
            prompt = FAILURE_PROMPT.format(query=original_query)
            
        final_text = await self.think(context="", goal=prompt)
        
        # STRICT VALIDATION: Reject JSON or Code Fences
        stripped_text = final_text.strip()
        if stripped_text.startswith("```") or stripped_text.startswith("{") or stripped_text.startswith("["):
            ctx.logger.warning(f"UserProxy received malformed output (JSON/Code Fence detected). Retrying with strict instruction.")
            # Simple retry logic: Append a strict instruction
            retry_prompt = prompt + "\n\nSYSTEM ALERT: PREVIOUS OUTPUT WAS REJECTED. DO NOT USE CODE FENCES. DO NOT OUTPUT JSON. RETURN ONLY RAW MARKDOWN."
            final_text = await self.think(context="", goal=retry_prompt)
            
            # If it fails again, fallback to a safe error message
            stripped_text = final_text.strip()
            if stripped_text.startswith("```") or stripped_text.startswith("{") or stripped_text.startswith("["):
                 ctx.logger.error("UserProxy failed to generate valid Markdown after retry.")
                 final_text = "I apologize, but I am having trouble formatting the answer correctly. Please try again."

        # Read the chat server URL from environment every time
        chat_server_url = os.getenv("CHAT_SERVER_URL", "http://127.0.0.1:8080/api/result")
        
        ctx.logger.info(f"Formatted final answer for request {msg.request_id}. Sending to chat server at {chat_server_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(chat_server_url, json={
                    "text": final_text,
                    "request_id": msg.request_id
                })
        except httpx.RequestError as e:
            ctx.logger.error(f"Failed to send result to chat server: {e}")
            # Log the final response to the console
            ctx.logger.error(f"response for request {msg.request_id}:\n{final_text}")

        # Clean up the stored query
        if msg.request_id in self._queries:
            del self._queries[msg.request_id]

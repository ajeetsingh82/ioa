# The User Proxy Agent: The "Speaker" and "Human Liaison"
import os
import requests
from uagents import Context
from .base import BaseAgent
from ..model.models import ArchitectResponse

class UserProxy(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "user_proxy"
        self._queries = {} # Store original queries by request_id

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
            final_text = await self.think(context="", goal=prompt)
        else:
            prompt = FAILURE_PROMPT.format(query=original_query)
            final_text = await self.think(context="", goal=prompt)
        
        # Read the chat server URL from environment every time
        chat_server_url = os.getenv("CHAT_SERVER_URL", "http://127.0.0.1:8080/api/result")
        
        ctx.logger.info(f"Formatted final answer for request {msg.request_id}. Sending to chat server at {chat_server_url}")
        
        try:
            requests.post(chat_server_url, json={
                "text": final_text,
                "request_id": msg.request_id
            })
        except requests.exceptions.RequestException as e:
            ctx.logger.error(f"Failed to send result to chat server: {e}")

        # Clean up the stored query
        if msg.request_id in self._queries:
            del self._queries[msg.request_id]

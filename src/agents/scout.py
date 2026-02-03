# The Scout Agent: The "Data Hunter"
import asyncio
from uagents import Context
from .base import BaseAgent
from ..model.models import AgentRegistration, ScoutRequest, ScoutResponse
from ..data.fetcher import search_web

class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "scout"
        self.on_message(model=ScoutRequest)(self.search)

    async def search(self, ctx: Context, sender: str, msg: ScoutRequest):
        """
        Performs a web search based on the sub-query and returns the raw content.
        """
        ctx.logger.debug(f"Scout received request: '{msg.sub_query}'")
        
        # Run the synchronous search_web function in a separate thread to avoid blocking
        content = await asyncio.to_thread(search_web, msg.sub_query)
        
        await ctx.send(sender, ScoutResponse(
            request_id=msg.request_id,
            content=content,
            label=msg.label
        ))

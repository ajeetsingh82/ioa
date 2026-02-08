# The Scout Agent: The "Data Hunter"
import asyncio
from uagents import Context
from .base import BaseAgent
from ..model.models import AgentRegistration, Thought
from ..data.fetcher import search_web

AGENT_TYPE_RETRIEVE = "RETRIEVE"

class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_RETRIEVE
        self.on_message(model=Thought)(self.search)

    async def search(self, ctx: Context, sender: str, msg: Thought):
        """
        Performs a web search based on the sub-query and returns the raw content.
        """
        if msg.type != "SEARCH":
            ctx.logger.warning(f"Scout received unknown message type: {msg.type}")
            return

        query = msg.content.strip()
        metadata = msg.metadata.copy() # Preserve metadata (like step_id)

        if not query:
            ctx.logger.warning("Scout received empty search query.")
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type="RETRIEVE",
                content="No search performed: Query was empty.",
                metadata=metadata
            ))
            return

        ctx.logger.debug(f"Scout received request: '{query}'")
        
        # Run the synchronous search_web function in a separate thread to avoid blocking
        content = await asyncio.to_thread(search_web, query)
        
        await ctx.send(sender, Thought(
            request_id=msg.request_id,
            type="RETRIEVE",
            content=content,
            metadata=metadata
        ))

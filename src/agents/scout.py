# The Scout Agent: The "Data Hunter"
import asyncio
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.fetcher import search_web
from ..cognition.cognition import shared_memory

AGENT_TYPE_SCOUT = "scout"

class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_SCOUT
        self.on_message(model=AgentGoal)(self.queued_handler(self.process_search))

    async def process_search(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Performs a web search and stores the result in shared memory using a descriptive, self-generated key.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Scout received unknown message type: {msg.type}")
            return

        ctx.logger.debug(f"Scout processing request for request_id: {msg.request_id}")
        
        try:
            query = shared_memory.get(f"{msg.request_id}:query")
            if not query:
                raise ValueError("Scout received empty search query.")

            content = await asyncio.to_thread(search_web, query)
            
            # Agent chooses a descriptive impression and generates its key.
            step_id = msg.metadata.get("step_id")
            impression = "retrieved_data"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, content)

            # Report the key of the new impression back to the conductor.
            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content="Scout task completed.",
                impressions=[output_key],
                metadata=response_metadata
            ))
        except Exception as e:
            ctx.logger.error(f"Scout failed during search: {e}")
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Search failed with error: {e}",
                metadata=msg.metadata
            ))

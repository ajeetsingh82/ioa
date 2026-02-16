import asyncio
import json
from uagents import Context

from ..data.documents import NamespaceBuilder
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.memory import memory
from ..cognition.cognition import shared_memory
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

RETRIEVE_COUNT = 5
COLLECTION_NAME = NamespaceBuilder.global_data(path=["scout", "crawler"])

class RetrieveAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.RETRIEVE
        
        config = agent_config_store.get_config(self.type.value)
        self.optimizer_prompt = config.get_prompt('optimizer') if config else None
            
        self.on_message(model=AgentGoal)(self.handle_retrieve_request)

    async def handle_retrieve_request(self, ctx: Context, sender: str, msg: AgentGoal):
        asyncio.create_task(self.process_retrieve(ctx, sender, msg))

    async def _optimize_query(self, query: str) -> str:
        if not self.optimizer_prompt:
            return query
        prompt = self.optimizer_prompt.format(query=query)
        optimized_query = await self.think(context="", goal=prompt)
        return optimized_query or query

    async def process_retrieve(self, ctx: Context, sender: str, msg: AgentGoal):
        if msg.type != AgentGoalType.TASK: return

        ctx.logger.info(f"Retrieve background task started for request: {msg.request_id}")
        
        try:
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query: 
                original_query = msg.content
            
            if not original_query:
                raise ValueError("Retrieve received empty query.")

            optimized_query = await self._optimize_query(original_query)
            ctx.logger.info(f"Optimized query: '{original_query}' -> '{optimized_query}'")

            # Query memory
            results = await asyncio.to_thread(
                memory.query, 
                collection_name=COLLECTION_NAME, 
                query_text=optimized_query, 
                n_results=RETRIEVE_COUNT
            )

            retrieved_texts = [res['document'] for res in results if res.get('document')]

            total_size = sum(len(text) for text in retrieved_texts)
            ctx.logger.info(f"Retrieved {len(retrieved_texts)} documents from memory. Total size: {total_size} characters.")

            step_id = msg.metadata.get("step_id")
            impression = "retrieved_context"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, json.dumps(retrieved_texts))

            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content=f"Retrieve task completed. Found {len(retrieved_texts)} relevant chunks.",
                impressions=[output_key],
                metadata={"goal_type": str(msg.type), "node_id": msg.metadata.get("node_id")}
            ))
        except Exception as e:
            ctx.logger.error(f"Retrieve failed: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Retrieve agent failed with error: {e}",
                metadata=msg.metadata
            ))

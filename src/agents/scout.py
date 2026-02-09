import asyncio
import json
from uagents import Context

from ..utils.utils import try_extract_text_from_html
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.fetcher import search_web_ddg, render_page_deep
from ..cognition.cognition import shared_memory
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

SEARCH_DEPTH = 10

class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SCOUT
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.optimizer_prompt = config.get_prompt('optimizer')
        if not self.optimizer_prompt:
            raise ValueError("Prompt 'optimizer' not found for agent type 'scout'.")
            
        self.on_message(model=AgentGoal)(self.handle_search_request)

    async def handle_search_request(self, ctx: Context, sender: str, msg: AgentGoal):
        asyncio.create_task(self.process_search(ctx, sender, msg))

    async def _optimize_query(self, query: str) -> str:
        prompt = self.optimizer_prompt.format(query=query)
        optimized_query = await self.think(context="", goal=prompt)
        return optimized_query or query

    async def process_search(self, ctx: Context, sender: str, msg: AgentGoal):
        if msg.type != AgentGoalType.TASK: return

        ctx.logger.info(f"Scout background task started for request: {msg.request_id}")
        
        try:
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query: raise ValueError("Scout received empty original query.")

            optimized_query = await self._optimize_query(original_query)
            ctx.logger.info(f"Optimized query: '{original_query}' -> '{optimized_query}'")

            search_results = await asyncio.to_thread(search_web_ddg, optimized_query, max_results=SEARCH_DEPTH)
            urls = [result['href'] for result in search_results if result.get('href')]

            render_tasks = [render_page_deep(url) for url in urls]
            rendered_pages = await asyncio.gather(*render_tasks)

            clean_texts = []
            for page in rendered_pages:
                if page and page.get('body'):
                    # Use the new, safer function name
                    clean_text = try_extract_text_from_html(page['body'])
                    if clean_text and len(clean_text) > 0:
                        ctx.logger.info(f"Extracted {len(clean_text)} clean text document.")
                        clean_texts.append(clean_text)
            
            total_chars = sum(len(text) for text in clean_texts)
            ctx.logger.info(f"Extracted {len(clean_texts)} clean text documents with a total of {total_chars} characters.")

            step_id = msg.metadata.get("step_id")
            impression = "clean_text_bodies"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, json.dumps(clean_texts))

            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content=f"Scout task completed. Found and cleaned {len(clean_texts)} pages.",
                impressions=[output_key],
                metadata={"goal_type": str(msg.type), "node_id": msg.metadata.get("node_id")}
            ))
        except Exception as e:
            ctx.logger.error(f"Scout failed during search: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Scout agent failed with error: {e}",
                metadata=msg.metadata
            ))

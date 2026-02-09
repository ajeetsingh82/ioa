import asyncio
import json
from uagents import Context

from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.fetcher import search_web_ddg, render_page_deep
from ..cognition.cognition import shared_memory
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

SEARCH_DEPTH = 3

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
            
        self.on_message(model=AgentGoal)(self.process_search)

    async def _optimize_query(self, query: str) -> str:
        """Uses an LLM to transform a conversational query into a search-engine-friendly query."""
        prompt = self.optimizer_prompt.format(query=query)
        optimized_query = await self.think(context="", goal=prompt)
        return optimized_query or query

    async def process_search(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Optimizes the user query, then performs a web search and deeply renders 
        the pages, storing the raw HTML bodies for the architect to process.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Scout received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Scout agent processing request: {msg.request_id}")
        
        try:
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query:
                raise ValueError("Scout received empty original query.")

            optimized_query = await self._optimize_query(original_query)
            ctx.logger.info(f"Optimized query: '{original_query}' -> '{optimized_query}'")

            search_results = await asyncio.to_thread(search_web_ddg, optimized_query, max_results=SEARCH_DEPTH)
            urls = [result['href'] for result in search_results if result.get('href')]

            render_tasks = [render_page_deep(url) for url in urls]
            rendered_pages = await asyncio.gather(*render_tasks)

            html_bodies = [page['body'] for page in rendered_pages if page and page.get('body')]
            
            step_id = msg.metadata.get("step_id")
            impression = "raw_html_bodies"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, json.dumps(html_bodies))

            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content=f"Scout task completed. Found {len(html_bodies)} pages for processing.",
                impressions=[output_key],
                metadata=response_metadata
            ))
        except Exception as e:
            ctx.logger.error(f"Scout failed during search: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Scout agent failed with error: {e}",
                metadata=msg.metadata
            ))

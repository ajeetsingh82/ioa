import asyncio
import json
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.fetcher import search_web_ddg
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store

json_parser = SafeJSONParser()
AGENT_TYPE_SCOUT = "scout"
depth = 10
class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_SCOUT
        
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.filter_prompt = config.get_prompt('filter')
        if not self.filter_prompt:
            raise ValueError("Prompt 'filter' not found for agent type 'retrieve'.")
            
        self.on_message(model=AgentGoal)(self.queued_handler(self.process_search_and_filter))

    async def _filter_content(self, query: str, content: str) -> str:
        """Uses LLM to filter a single piece of content."""
        prompt = self.filter_prompt.format(query=query, context=content)
        llm_response = await self.think(context="", goal=prompt)
        
        parsed = json_parser.parse(llm_response)
        return parsed.get("content", "")

    async def process_search_and_filter(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Performs a web search, filters the results in parallel, and stores a list of chunks.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Scout received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Scout agent processing request: {msg.request_id}")
        
        try:
            query = shared_memory.get(f"{msg.request_id}:query")
            if not query:
                raise ValueError("Scout received empty search query.")

            # 1. Fetch multiple web results
            # The `search_web_ddg` function needs to be defined in fetcher.py to return multiple results
            search_results = await asyncio.to_thread(search_web_ddg, query, max_results=depth)
            
            # 2. Create parallel filtering tasks for each result
            filter_tasks = []
            for result in search_results:
                # Assuming result is a dict with a 'body' key containing the page content
                if result.get('body'):
                    filter_tasks.append(self._filter_content(query, result['body']))
            
            # 3. Execute filtering in parallel
            filtered_chunks = await asyncio.gather(*filter_tasks)
            
            # Filter out any empty strings from failed extractions
            final_chunks = [chunk for chunk in filtered_chunks if chunk]
            
            # 4. Store the list of filtered chunks in shared memory
            step_id = msg.metadata.get("step_id")
            impression = "filtered_web_results"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            # We need to store the list as a JSON string
            shared_memory.set(output_key, json.dumps(final_chunks))

            # 5. Report completion
            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content=f"Scout task completed. Found {len(final_chunks)} relevant chunks.",
                impressions=[output_key],
                metadata=response_metadata
            ))
        except Exception as e:
            ctx.logger.error(f"Scout failed during search and filter: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Scout agent failed with error: {e}",
                metadata=msg.metadata
            ))

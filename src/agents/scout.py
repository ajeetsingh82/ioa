import asyncio
import json
from uagents import Context
from bs4 import BeautifulSoup

from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..data.fetcher import search_web_ddg, render_page_deep
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

json_parser = SafeJSONParser()
SEARCH_DEPTH = 3
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

class ScoutAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SCOUT
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.filter_prompt = config.get_prompt('filter')
        if not self.filter_prompt:
            raise ValueError("Prompt 'filter' not found for agent type 'scout'.")
            
        self.on_message(model=AgentGoal)(self.queued_handler(self.process_search_and_filter))

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """Splits text into overlapping chunks."""
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    async def _filter_chunk(self, query: str, chunk: str) -> str:
        """Uses LLM to filter a single chunk of text."""
        prompt = self.filter_prompt.format(query=query, context=chunk)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        return parsed.get("content", "")

    async def _filter_content(self, query: str, html_body: str) -> str:
        """
        Extracts clean text, chunks it, and filters each chunk in parallel.
        """
        if not html_body:
            return ""
            
        soup = BeautifulSoup(html_body, 'html.parser')
        clean_text = soup.get_text(separator='\n', strip=True)
        
        if not clean_text:
            return ""

        # 1. Split the clean text into chunks
        chunks = self._split_text_into_chunks(clean_text)
        
        # 2. Create parallel filtering tasks for each chunk
        filter_tasks = [self._filter_chunk(query, chunk) for chunk in chunks]
        
        # 3. Execute filtering in parallel
        relevant_snippets = await asyncio.gather(*filter_tasks)
        
        # 4. Join the relevant snippets into a single block of text
        return "\n".join(snippet for snippet in relevant_snippets if snippet)

    async def process_search_and_filter(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Performs a web search, deeply renders pages, and filters the content in parallel.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Scout received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Scout agent processing request: {msg.request_id}")
        
        try:
            query = shared_memory.get(f"{msg.request_id}:query")
            if not query:
                raise ValueError("Scout received empty search query.")

            search_results = await asyncio.to_thread(search_web_ddg, query, max_results=SEARCH_DEPTH)
            urls = [result['href'] for result in search_results if result.get('href')]

            render_tasks = [render_page_deep(url) for url in urls]
            rendered_pages = await asyncio.gather(*render_tasks)

            # This now runs the advanced chunking and filtering for each page
            filter_tasks = []
            for page_data in rendered_pages:
                if page_data and page_data.get('body'):
                    filter_tasks.append(self._filter_content(query, page_data['body']))
            
            filtered_chunks = await asyncio.gather(*filter_tasks)
            
            final_chunks = [chunk for chunk in filtered_chunks if chunk]
            
            step_id = msg.metadata.get("step_id")
            impression = "filtered_web_results"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, json.dumps(final_chunks))

            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content=f"Scout task completed. Found {len(final_chunks)} relevant chunks from {len(urls)} sources.",
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

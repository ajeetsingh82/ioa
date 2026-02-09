import ast
import json
import asyncio
from uagents import Context
from bs4 import BeautifulSoup

from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

json_parser = SafeJSONParser()
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SYNTHESIZE
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.default_prompt = config.get_prompt('default')
        self.summarize_prompt = config.get_prompt('summarize_chunk')
        if not self.default_prompt or not self.summarize_prompt:
            raise ValueError(f"Required prompts not found for agent type '{self.type.value}'.")

        self.on_message(model=AgentGoal)(self.process_synthesis)

    def _split_text_into_chunks(self, text: str) -> list[str]:
        if not text: return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    async def _summarize_chunk(self, query: str, chunk: str) -> str:
        """Filters and summarizes a single chunk of text (Map step)."""
        if not chunk: return ""
        prompt = self.summarize_prompt.format(query=query, context=chunk)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        return parsed.get("summary", "")

    async def _process_html_body(self, query: str, html_body: str) -> str:
        """Extracts text, chunks, and summarizes a single HTML body."""
        if not html_body: return ""
        
        soup = BeautifulSoup(html_body, 'html.parser')
        clean_text = soup.get_text(separator='\n', strip=True)
        if not clean_text: return ""

        chunks = self._split_text_into_chunks(clean_text)
        summarize_tasks = [self._summarize_chunk(query, chunk) for chunk in chunks]
        chunk_summaries = await asyncio.gather(*summarize_tasks)
        
        return "\n".join(summary for summary in chunk_summaries if summary)

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Performs a full Map-Reduce synthesis from raw HTML bodies.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Architect received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Architect processing synthesis for request: {msg.request_id}")

        try:
            input_keys = ast.literal_eval(msg.content)
            if not input_keys: raise ValueError("Architect received no input keys.")

            html_bodies_json = shared_memory.get(input_keys[0])
            html_bodies = json.loads(html_bodies_json)
            
            ctx.logger.info(f"Received {len(html_bodies)} HTML documents to process.")

            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query: raise ValueError("Original query not found.")

            synthesized_data = "Insufficient information gathered to form an answer."

            if html_bodies:
                page_summary_tasks = [self._process_html_body(original_query, body) for body in html_bodies]
                page_summaries = await asyncio.gather(*page_summary_tasks)
                
                final_context = "\n\n---\n\n".join(summary for summary in page_summaries if summary)
                
                ctx.logger.info(f"Total size of summarized context: {len(final_context)} characters.")

                if final_context:
                    final_prompt = self.default_prompt.format(query=original_query, context=final_context)
                    llm_response = await self.think(context="", goal=final_prompt)
                    response_json = json_parser.parse(llm_response)
                    
                    if "answer" in response_json:
                        synthesized_data = response_json["answer"]
                    else:
                        synthesized_data = llm_response
            
            step_id = msg.metadata.get("step_id")
            impression = "final_answer"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, synthesized_data)

            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content="Architect task completed.",
                impressions=[output_key],
                metadata={"goal_type": str(msg.type), "node_id": msg.metadata.get("node_id")}
            ))
        except Exception as e:
            ctx.logger.error(f"Architect failed during synthesis: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Synthesis failed with error: {e}",
                metadata=msg.metadata
            ))

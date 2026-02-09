import ast
import json
import asyncio
from uagents import Context

from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

json_parser = SafeJSONParser()
CHUNK_SIZE = 8000
CHUNK_OVERLAP = 400
CONTEXT_THRESHOLD = 16000

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SYNTHESIZE
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.default_prompt = config.get_prompt('default')
        self.summarize_prompt = config.get_prompt('summarize_chunk')
        self.meta_prompt = config.get_prompt('meta_summarize')
        if not all([self.default_prompt, self.summarize_prompt, self.meta_prompt]):
            raise ValueError(f"Required prompts not found for agent type '{self.type.value}'.")

        self.on_message(model=AgentGoal)(self.handle_synthesis_request)

    async def handle_synthesis_request(self, ctx: Context, sender: str, msg: AgentGoal):
        asyncio.create_task(self.process_synthesis(ctx, sender, msg))

    def _split_text_into_chunks(self, text: str, size: int, overlap: int) -> list[str]:
        if not text: return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + size
            chunks.append(text[start:end])
            start += size - overlap
        return chunks

    async def _summarize_chunk(self, query: str, chunk: str, prompt_template: str) -> str:
        if not chunk: return ""
        prompt = prompt_template.format(query=query, context=chunk)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        if isinstance(parsed, dict):
            return parsed.get("summary", "")
        return ""

    async def _recursive_reduce(self, query: str, summaries: list[str]) -> str:
        combined_text = "\n\n---\n\n".join(summaries)
        self._logger.info(f"Recursive reduce called with {len(summaries)} summaries, total size: {len(combined_text)} chars.")
        
        if len(combined_text) <= CONTEXT_THRESHOLD:
            return combined_text

        self._logger.info(f"Context size exceeds threshold. Starting next reduction.")
        
        new_chunks = self._split_text_into_chunks(combined_text, CHUNK_SIZE, CHUNK_OVERLAP)
        meta_summarize_tasks = [self._summarize_chunk(query, chunk, self.meta_prompt) for chunk in new_chunks]
        new_summaries = await asyncio.gather(*meta_summarize_tasks)
        
        return await self._recursive_reduce(query, [s for s in new_summaries if s])

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):
        if msg.type != AgentGoalType.TASK: return

        ctx.logger.info(f"Architect background task started for request: {msg.request_id}")
        try:
            input_keys = ast.literal_eval(msg.content)
            if not input_keys: raise ValueError("Architect received no input keys.")

            # Now receives a list of clean text bodies
            clean_texts = json.loads(shared_memory.get(input_keys[0]))
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query: raise ValueError("Original query not found.")

            ctx.logger.info(f"Received {len(clean_texts)} clean text documents to process.")
            synthesized_data = "Insufficient information gathered to form an answer."

            if clean_texts:
                # Map: Chunk and summarize each clean text document in parallel
                page_summary_tasks = []
                for text in clean_texts:
                    chunks = self._split_text_into_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
                    self._logger.info(f"Split one document into {len(chunks)} chunks.")
                    page_summary_tasks.extend([self._summarize_chunk(original_query, chunk, self.summarize_prompt) for chunk in chunks])
                
                initial_summaries = await asyncio.gather(*page_summary_tasks)
                initial_summaries = [s for s in initial_summaries if s]
                
                initial_context_size = len("\n\n---\n\n".join(initial_summaries))
                ctx.logger.info(f"Generated {len(initial_summaries)} initial summaries with a combined size of {initial_context_size} chars.")
                
                # Reduce: Recursively summarize the summaries
                final_context = await self._recursive_reduce(original_query, initial_summaries)
                
                ctx.logger.info(f"Final context size after reduction: {len(final_context)} characters.")

                if final_context:
                    final_prompt = self.default_prompt.format(query=original_query, context=final_context)
                    llm_response = await self.think(context="", goal=final_prompt)
                    response_json = json_parser.parse(llm_response)
                    synthesized_data = response_json.get("answer", llm_response)
            
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

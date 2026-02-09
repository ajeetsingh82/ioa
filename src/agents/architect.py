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
CHUNK_SIZE = 12000
CHUNK_OVERLAP = 500
# This threshold now applies to the number of facts, not characters
FACT_THRESHOLD = 50 

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SYNTHESIZE
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.extract_prompt = config.get_prompt('extract_relevant_facts')
        self.combine_prompt = config.get_prompt('combine_facts')
        self.synthesis_prompt = config.get_prompt('synthesize_answer')
        if not all([self.extract_prompt, self.combine_prompt, self.synthesis_prompt]):
            raise ValueError(f"Required prompts not found for agent type '{self.type.value}'.")

        self.on_message(model=AgentGoal)(self.handle_synthesis_request)

    async def handle_synthesis_request(self, ctx: Context, sender: str, msg: AgentGoal):
        asyncio.create_task(self.process_synthesis(ctx, sender, msg))

    def _split_text_into_chunks(self, text: str) -> list[str]:
        if not text: return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    async def _extract_facts_from_chunk(self, query: str, chunk: str) -> list[str]:
        """Extracts a list of facts from a chunk. Guaranteed to return a list."""
        if not chunk: return []
        prompt = self.extract_prompt.format(query=query, context=chunk)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        if isinstance(parsed, dict):
            facts = parsed.get("facts", [])
            return facts if isinstance(facts, list) else [facts]
        return []

    async def _combine_facts(self, query: str, facts_to_combine: list) -> list[str]:
        """Uses an LLM to combine and deduplicate lists of facts."""
        context = json.dumps(facts_to_combine, indent=2)
        prompt = self.combine_prompt.format(query=query, context=context)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        if isinstance(parsed, dict):
            return parsed.get("facts", [])
        return []

    async def _recursive_reduce(self, query: str, facts: list) -> list:
        """Recursively reduces a list of facts until it's under the threshold."""
        if len(facts) <= FACT_THRESHOLD:
            return facts

        self._logger.info(f"Fact count ({len(facts)}) exceeds threshold of {FACT_THRESHOLD}. Starting reduction.")
        
        # Batch facts for combination
        batched_facts = [facts[i:i + 5] for i in range(0, len(facts), 5)] # Combine 5 lists at a time
        
        combine_tasks = [self._combine_facts(query, batch) for batch in batched_facts]
        new_fact_lists = await asyncio.gather(*combine_tasks)
        
        # Flatten the list of lists into a single list
        combined_facts = [fact for sublist in new_fact_lists for fact in sublist]
        
        return await self._recursive_reduce(query, combined_facts)

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):
        if msg.type != AgentGoalType.TASK: return

        ctx.logger.info(f"Architect background task started for request: {msg.request_id}")
        try:
            input_keys = ast.literal_eval(msg.content)
            if not input_keys: raise ValueError("Architect received no input keys.")

            clean_texts = json.loads(shared_memory.get(input_keys[0]))
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query: raise ValueError("Original query not found.")

            ctx.logger.info(f"Received {len(clean_texts)} clean text documents to process.")
            synthesized_data = "Insufficient information gathered to form an answer."

            if clean_texts:
                full_text_stream = "\n\n--- NEW DOCUMENT ---\n\n".join(clean_texts)
                chunks = self._split_text_into_chunks(full_text_stream)
                
                fact_extraction_tasks = [self._extract_facts_from_chunk(original_query, chunk) for chunk in chunks]
                initial_fact_lists = await asyncio.gather(*fact_extraction_tasks)
                
                # Flatten the list of lists into a single list of individual facts
                initial_facts = [fact for sublist in initial_fact_lists for fact in sublist]
                ctx.logger.info(f"Extracted a total of {len(initial_facts)} facts from all chunks.")
                
                # Reduce: Recursively combine the facts
                final_facts = await self._recursive_reduce(original_query, initial_facts)
                ctx.logger.info(f"Reduced to {len(final_facts)} consolidated facts.")

                if final_facts:
                    final_context = "\n".join(f"- {fact}" for fact in final_facts)
                    final_prompt = self.synthesis_prompt.format(query=original_query, context=final_context)
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

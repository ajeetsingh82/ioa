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

    async def _summarize_chunk(self, query: str, chunk: str) -> str:
        """Summarizes a single chunk of text (Map step)."""
        if not chunk:
            return ""
        prompt = self.summarize_prompt.format(query=query, context=chunk)
        llm_response = await self.think(context="", goal=prompt)
        parsed = json_parser.parse(llm_response)
        return parsed.get("summary", "")

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Performs a hierarchical summarization (Map-Reduce) to synthesize the final answer.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Architect received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Architect processing synthesis for request: {msg.request_id}")

        try:
            input_keys = ast.literal_eval(msg.content)
            if not input_keys:
                raise ValueError("Architect received no input keys.")

            filtered_chunks_json = shared_memory.get(input_keys[0])
            filtered_chunks = json.loads(filtered_chunks_json)
            
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query:
                raise ValueError("Original query not found in shared memory.")

            synthesized_data = "Insufficient information gathered to form an answer."

            if filtered_chunks:
                # 1. Map: Summarize each chunk in parallel
                summarize_tasks = [self._summarize_chunk(original_query, chunk) for chunk in filtered_chunks]
                chunk_summaries = await asyncio.gather(*summarize_tasks)
                
                # 2. Reduce: Combine summaries and generate the final answer
                final_context = "\n\n---\n\n".join(summary for summary in chunk_summaries if summary)
                
                if final_context:
                    final_prompt = self.default_prompt.format(query=original_query, context=final_context)
                    llm_response = await self.think(context="", goal=final_prompt)
                    response_json = json_parser.parse(llm_response)
                    
                    if "answer" in response_json:
                        synthesized_data = response_json["answer"]
                    else:
                        ctx.logger.error("Architect parser fallback on final answer. Using raw response.")
                        synthesized_data = llm_response
            
            step_id = msg.metadata.get("step_id")
            impression = "final_answer"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, synthesized_data)

            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content="Architect task completed.",
                impressions=[output_key],
                metadata=response_metadata
            ))
        except Exception as e:
            ctx.logger.error(f"Architect failed during synthesis: {e}", exc_info=True)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Synthesis failed with error: {e}",
                metadata=msg.metadata
            ))

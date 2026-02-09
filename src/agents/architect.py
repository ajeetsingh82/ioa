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

# Tunables
CHUNK_SIZE = 9000
CHUNK_OVERLAP = 300
CONTEXT_THRESHOLD = 15000
MAX_CONDENSE_ATTEMPTS = 4
MIN_SHRINK_RATIO = 0.85
LLM_TIMEOUT = 60  # seconds


class ArchitectAgent(BaseAgent):

    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.SYNTHESIZE

        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for '{self.type.value}' not found.")

        self.synthesis_prompt = config.get_prompt('default')

        if not self.synthesis_prompt:
            raise ValueError("Required prompts missing for SYNTHESIZE agent.")

        self.on_message(model=AgentGoal)(self.handle_synthesis_request)

    async def handle_synthesis_request(self, ctx: Context, sender: str, msg: AgentGoal):
        asyncio.create_task(self.process_synthesis(ctx, sender, msg))

    # --------------------------------
    # Utilities
    # --------------------------------

    def _split_text_into_chunks(self, text: str) -> list[str]:
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _safe_parse_json(self, response: str, key: str):
        try:
            parsed = json_parser.parse(response)
            if isinstance(parsed, dict):
                return parsed.get(key)
        except Exception:
            pass
        return None

    def _hard_truncate(self, text: str) -> str:
        return text[:CONTEXT_THRESHOLD]

    async def _safe_llm_call(self, prompt: str) -> str:
        """
        LLM wrapper with timeout + failure isolation.
        """
        try:
            return await asyncio.wait_for(
                self.think(context="", goal=prompt),
                timeout=LLM_TIMEOUT
            )
        except Exception as e:
            self._logger.warning(f"LLM call failed: {e}")
            return ""

    # --------------------------------
    # Controlled Condense (Resilient)
    # --------------------------------

    async def _condense_context(self, query: str, context: str) -> str:

        attempt = 0
        current = context

        while len(current) > CONTEXT_THRESHOLD and attempt < MAX_CONDENSE_ATTEMPTS:

            try:
                prompt = self.synthesis_prompt.format(
                    query=query,
                    context=current,
                    char_limit=CONTEXT_THRESHOLD
                )

                response = await self._safe_llm_call(prompt)

                if not response:
                    self._logger.warning("Empty condense response.")
                    return self._hard_truncate(current)

                condensed = self._safe_parse_json(response, "condensed_text")
                if not condensed:
                    condensed = response

                if len(condensed) > CONTEXT_THRESHOLD:
                    condensed = condensed[:CONTEXT_THRESHOLD]

                shrink_ratio = len(condensed) / len(current)

                if shrink_ratio > MIN_SHRINK_RATIO:
                    self._logger.warning("Condense ineffective. Forcing truncate.")
                    return self._hard_truncate(condensed)

                current = condensed
                attempt += 1

            except Exception as e:
                self._logger.warning(f"Condense attempt failed: {e}")
                return self._hard_truncate(current)

        if len(current) > CONTEXT_THRESHOLD:
            return self._hard_truncate(current)

        return current

    # --------------------------------
    # Main Processing (Failure Tolerant)
    # --------------------------------

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):

        if msg.type != AgentGoalType.TASK:
            return

        ctx.logger.info(f"Architect started: {msg.request_id}")

        synthesized_data = "Insufficient information gathered."

        try:
            input_keys = ast.literal_eval(msg.content)
            if not input_keys:
                raise ValueError("No input keys provided.")

            raw = shared_memory.get(input_keys[0])
            clean_texts = json.loads(raw) if raw else []

            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query:
                raise ValueError("Original query missing.")

            if not clean_texts:
                raise ValueError("No documents found.")

            full_stream = "\n\n--- NEW DOCUMENT ---\n\n".join(clean_texts)
            chunks = self._split_text_into_chunks(full_stream)

            running_context = ""
            seen_chunks = set()

            ctx.logger.info(f"Processing {len(chunks)} chunks.")

            for i, chunk in enumerate(chunks):

                try:
                    if chunk in seen_chunks:
                        continue
                    seen_chunks.add(chunk)

                    candidate = running_context + "\n\n" + chunk

                    if len(candidate) > CONTEXT_THRESHOLD:
                        running_context = await self._condense_context(
                            original_query,
                            running_context
                        )
                        candidate = running_context + "\n\n" + chunk

                    if len(candidate) > CONTEXT_THRESHOLD:
                        candidate = candidate[:CONTEXT_THRESHOLD]

                    running_context = candidate

                except Exception as chunk_error:
                    ctx.logger.warning(
                        f"Chunk {i} failed, continuing. Error: {chunk_error}"
                    )
                    continue

            # Final guard
            if len(running_context) > CONTEXT_THRESHOLD:
                running_context = await self._condense_context(
                    original_query,
                    running_context
                )

            synthesized_data = running_context.strip()

        except Exception as e:
            ctx.logger.error(f"Architect partial failure: {e}")

        # Always respond (never abort)
        step_id = msg.metadata.get("step_id")
        output_key = f"{msg.request_id}:{step_id}:final_answer"
        shared_memory.set(output_key, synthesized_data)

        await ctx.send(
            sender,
            Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content="Architect completed (best effort).",
                impressions=[output_key],
                metadata={
                    "goal_type": str(msg.type),
                    "node_id": msg.metadata.get("node_id")
                }
            )
        )

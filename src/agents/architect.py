# The Architect Agent: The "Synthesis" or "Reduce" phase.
from uagents import Context
from .base import BaseAgent
from ..model.models import ArchitectRequest, ArchitectResponse
from ..cognition.cognition import shared_memory
from ..prompt.prompt import ARCHITECT_PROMPT

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "architect"
        self.on_message(model=ArchitectRequest)(self.synthesize_answer)

    async def synthesize_answer(self, ctx: Context, sender: str, msg: ArchitectRequest):
        """
        Assembles data from working memory and synthesizes it into a factual block.
        """
        ctx.logger.info(f"Architect received synthesis request for: '{msg.original_query}'")

        context = ""
        for label in msg.labels:
            retrieved_data = shared_memory.get(f"{msg.request_id}:{label}")
            if retrieved_data and "Could not retrieve" not in retrieved_data:
                context += f"--- Context for '{label}' ---\n{retrieved_data}\n\n"
        
        if not context:
            synthesized_data = "Insufficient information gathered to form an answer."
            status = "failure"
        else:
            prompt = ARCHITECT_PROMPT.format(query=msg.original_query, context=context)
            synthesized_data = await self.think(context="", goal=prompt)
            status = "success"

        await ctx.send(sender, ArchitectResponse(
            request_id=msg.request_id,
            status=status,
            synthesized_data=synthesized_data
        ))
        ctx.logger.info("Synthesis complete. Sending structured response to Conductor.")

        for label in msg.labels:
            shared_memory.delete(f"{msg.request_id}:{label}")
        ctx.logger.info(f"Cleaned up working memory for request: {msg.request_id}")

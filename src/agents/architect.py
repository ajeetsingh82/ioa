# The Architect Agent: The "Synthesis" or "Reduce" phase.
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_SYNTHESIZE = "synthesize"

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_SYNTHESIZE
        
        # Load configuration from the central store using the agent's type
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.prompt = config.get_prompt('default')
        if not self.prompt:
            raise ValueError(f"Prompt 'default' not found for agent type '{self.type}'.")

        self.on_message(model=Thought)(self.synthesize_answer)

    async def synthesize_answer(self, ctx: Context, sender: str, msg: Thought):
        """
        Assembles data from working memory and synthesizes it into a factual block.
        """
        if msg.type != "SYNTHESIZE":
            ctx.logger.warning(f"Architect received unknown message type: {msg.type}")
            return

        original_query = msg.metadata.get("original_query", "")
        labels_str = msg.metadata.get("labels", "")
        labels = [l.strip() for l in labels_str.split(",") if l.strip()]
        metadata = msg.metadata.copy()

        ctx.logger.debug(f"Architect received synthesis request for: '{original_query}'")

        context = ""
        for label in labels:
            retrieved_data = shared_memory.get(f"{msg.request_id}:{label}")
            if retrieved_data and "Could not retrieve" not in retrieved_data:
                context += f"--- Context for '{label}' ---\n{retrieved_data}\n\n"
        
        status = "failure"
        synthesized_data = "Insufficient information gathered to form an answer."

        if context:
            prompt = self.prompt.format(query=original_query, context=context)
            
            llm_response = await self.think(context="", goal=prompt)
            response_json = json_parser.parse(llm_response)
            
            # The parser guarantees a dict, so we just check for the key
            if "answer" in response_json:
                synthesized_data = response_json["answer"]
                status = "success"
            else:
                # This case should be rare due to the parser's fallback
                ctx.logger.error(f"Architect parser fallback was triggered, but key 'answer' is missing. Raw response: {llm_response}")
                synthesized_data = llm_response # Send raw response as a last resort

        metadata["status"] = status
        await ctx.send(sender, Thought(
            request_id=msg.request_id,
            type="RESPONSE",
            content=synthesized_data,
            metadata=metadata
        ))
        ctx.logger.debug(f"Synthesis complete. Status: {status}.")

        # Clean up working memory
        for label in labels:
            shared_memory.delete(f"{msg.request_id}:{label}")
        ctx.logger.debug(f"Cleaned up working memory for request: {msg.request_id}")

# The Filter Agent: The "Semantic Sieve"
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_FILTER = "FILTER"

class FilterAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_FILTER
        
        # Load configuration from the central store
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.specialized_prompt = config.get_prompt('specialized')
        self.general_prompt = config.get_prompt('general')
        if not self.specialized_prompt or not self.general_prompt:
            raise ValueError(f"Required prompts ('specialized', 'general') not found for agent type '{self.type}'.")

        self.on_message(model=Thought)(self.filter_content)

    async def filter_content(self, ctx: Context, sender: str, msg: Thought):
        """
        Filters raw content using its cognitive ability and stores the result.
        """
        if msg.type != "FILTER":
            ctx.logger.warning(f"Filter received unknown message type: {msg.type}")
            return

        label = msg.metadata.get("label", "general")
        original_query = msg.metadata.get("original_query", "")
        metadata = msg.metadata.copy()

        ctx.logger.info(f"Filter agent received content for label: '{label}'")

        if label != "general":
            prompt = self.specialized_prompt.format(label=label)
        else:
            prompt = self.general_prompt.format(query=original_query)

        llm_response = await self.think(context=msg.content, goal=prompt)
        response_json = json_parser.parse(llm_response)

        # The parser guarantees a dict, so we just check for the key
        if "content" in response_json:
            filtered_content = response_json["content"]
        else:
            # This case should be rare due to the parser's fallback
            ctx.logger.debug(f"Filter parser fallback was triggered, but key 'content' is missing. Using raw response.")
            filtered_content = response_json.get("answer", llm_response) # Use fallback key or raw text

        ctx.logger.info(f"Filtered content. Original length: {len(msg.content)}, New length: {len(filtered_content)}")

        shared_memory.set(f"{msg.request_id}:{label}", filtered_content)
        
        # Send a Thought back to signal completion
        await ctx.send(sender, Thought(
            request_id=msg.request_id,
            type=self.type,
            content="Task Completed",
            metadata=metadata
        ))

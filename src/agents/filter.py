# The Filter Agent: The "Semantic Sieve"
from uagents import Context
from .base import BaseAgent
from ..model.models import CognitiveMessage
from ..cognition.cognition import shared_memory
from ..prompt.prompt import FILTER_PROMPT, GENERAL_FILTER_PROMPT
from ..utils.json_parser import SafeJSONParser

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_FILTER = "FILTER"

class FilterAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_FILTER
        self.on_message(model=CognitiveMessage)(self.filter_content)

    async def filter_content(self, ctx: Context, sender: str, msg: CognitiveMessage):
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
            prompt = FILTER_PROMPT.format(label=label)
        else:
            prompt = GENERAL_FILTER_PROMPT.format(query=original_query)

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
        
        # Send a CognitiveMessage back to signal completion
        await ctx.send(sender, CognitiveMessage(
            request_id=msg.request_id,
            type="FILTER",
            content="Task Completed",
            metadata=metadata
        ))

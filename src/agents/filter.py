# The Filter Agent: The "Semantic Sieve"
from uagents import Context
from .base import BaseAgent
from ..model.models import FilterRequest, TaskCompletion
from ..cognition.cognition import shared_memory
from ..prompt.prompt import FILTER_PROMPT, GENERAL_FILTER_PROMPT
from ..utils.json_parser import SafeJSONParser

# Instantiate the parser
json_parser = SafeJSONParser()

class FilterAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "filter"
        self.on_message(model=FilterRequest)(self.filter_content)

    async def filter_content(self, ctx: Context, sender: str, msg: FilterRequest):
        """
        Filters raw content using its cognitive ability and stores the result.
        """
        ctx.logger.info(f"Filter agent received content for label: '{msg.label}'")

        if msg.label != "general":
            prompt = FILTER_PROMPT.format(label=msg.label)
        else:
            prompt = GENERAL_FILTER_PROMPT.format(query=msg.original_query)

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

        shared_memory.set(f"{msg.request_id}:{msg.label}", filtered_content)
        
        await ctx.send(sender, TaskCompletion(request_id=msg.request_id, label=msg.label))

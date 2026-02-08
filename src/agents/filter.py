# The Filter Agent: The "Semantic Sieve"
import ast
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_FILTER = "filter"

class FilterAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_FILTER
        
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.prompt = config.get_prompt('general')
        if not self.prompt:
            raise ValueError(f"Required prompt ('general') not found for agent type '{self.type}'.")

        self.on_message(model=AgentGoal)(self.queued_handler(self.process_filter))

    async def process_filter(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Filters content from shared memory and stores the result using a descriptive, self-generated key.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Filter received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Filter agent processing request: {msg.request_id}")

        try:
            input_keys = ast.literal_eval(msg.content)
            retrieved_data_key = input_keys[0]
            retrieved_data = shared_memory.get(retrieved_data_key)
            
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query:
                raise ValueError("Original query not found in shared memory.")

            prompt = self.prompt.format(query=original_query)
            llm_response = await self.think(context=retrieved_data, goal=prompt)
            response_json = json_parser.parse(llm_response)

            if "content" in response_json:
                filtered_content = response_json["content"]
            else:
                ctx.logger.debug(f"Filter parser fallback. Using raw response.")
                filtered_content = response_json.get("answer", llm_response)

            # Agent chooses a descriptive impression and generates its key.
            step_id = msg.metadata.get("step_id")
            impression = "filtered_chunks"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, filtered_content)
            
            # Report the key of the new impression back to the conductor.
            response_metadata = msg.metadata.copy()
            response_metadata["goal_type"] = str(msg.type)
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.RESOLVED,
                content="Filter task completed.",
                impressions=[output_key],
                metadata=response_metadata
            ))
        except Exception as e:
            ctx.logger.error(f"Filter failed during processing: {e}")
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Filter failed with error: {e}",
                metadata=msg.metadata
            ))

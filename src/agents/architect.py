# The Architect Agent: The "Synthesis" or "Reduce" phase.
import ast
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..cognition.cognition import shared_memory
from ..utils.json_parser import SafeJSONParser
from ..config.store import agent_config_store

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_SYNTHESIZE = "synthesize"

class ArchitectAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_SYNTHESIZE
        
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.prompt = config.get_prompt('default')
        if not self.prompt:
            raise ValueError(f"Prompt 'default' not found for agent type '{self.type}'.")

        self.on_message(model=AgentGoal)(self.queued_handler(self.process_synthesis))

    async def process_synthesis(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Synthesizes an answer and stores it in shared memory using a descriptive, self-generated key.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"Architect received unknown message type: {msg.type}")
            return

        ctx.logger.debug(f"Architect processing synthesis for request: {msg.request_id}")

        try:
            input_keys = ast.literal_eval(msg.content)
            filtered_data_key = input_keys[0]
            context = shared_memory.get(filtered_data_key)
            
            original_query = shared_memory.get(f"{msg.request_id}:query")
            if not original_query:
                raise ValueError("Original query not found in shared memory.")

            synthesized_data = "Insufficient information gathered to form an answer."

            if context:
                prompt = self.prompt.format(query=original_query, context=context)
                llm_response = await self.think(context="", goal=prompt)
                response_json = json_parser.parse(llm_response)
                
                if "answer" in response_json:
                    synthesized_data = response_json["answer"]
                else:
                    ctx.logger.error(f"Architect parser fallback. Using raw response.")
                    synthesized_data = llm_response

            # Agent chooses a descriptive impression and generates the final answer key.
            step_id = msg.metadata.get("step_id")
            impression = "final_answer"
            output_key = f"{msg.request_id}:{step_id}:{impression}"
            shared_memory.set(output_key, synthesized_data)

            # Report the final answer key back to the conductor.
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
            ctx.logger.error(f"Architect failed during synthesis: {e}")
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Synthesis failed with error: {e}",
                metadata=msg.metadata
            ))

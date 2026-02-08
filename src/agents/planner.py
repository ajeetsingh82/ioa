# The Planner Agent: The "Brain" of the operation.
import json

import yaml
from uagents import Context
from .base import BaseAgent
from ..model.models import AgentGoal, Thought, AgentGoalType, ThoughtType
from ..config.store import agent_config_store
from ..utils.json_parser import SafeJSONParser

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_PLANNER = "planner"

class PlannerAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_PLANNER
        
        # Load configuration from the central store with an exact match
        self.config = agent_config_store.get_config(self.type)
        if not self.config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")

        if not self.config.get_prompt():
            raise ValueError(f"Prompt not found for agent type '{self.type}'.")
        
        # Register the handler for planning goals
        self.on_message(model=AgentGoal)(self.queued_handler(self.process_planning_request))

    async def process_planning_request(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Decomposes the user query into a graph of tasks and returns it as a Thought.
        """
        if msg.type != AgentGoalType.PLAN:
            ctx.logger.warning(f"Planner received unknown goal type: {msg.type}")
            await ctx.send(sender, Thought(
                request_id=msg.request_id,
                type=ThoughtType.FAILED,
                content=f"Invalid goal type for Planner: {msg.type}",
                metadata=msg.metadata
            ))
            return

        ctx.logger.debug(f"Planner processing query: '{msg.content}'")

        plan =  yaml.safe_dump(self.config.get_schema("fixed_plan_json"))

        # Include original goal type in metadata for the Conductor
        response_metadata = msg.metadata.copy()
        response_metadata["goal_type"] = str(msg.type)

        # Send the graph back to the Conductor as a Thought
        await ctx.send(sender, Thought(
            request_id=msg.request_id,
            type=ThoughtType.RESOLVED,
            content=plan,
            metadata=response_metadata
        ))

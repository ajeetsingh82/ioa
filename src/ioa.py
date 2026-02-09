from uagents import Agent, Context

from .model.agent_types import AgentType
from .agent_registry import agent_registry
from .model.models import (
    AgentRegistration, Thought, AgentGoal, UserQuery, ReplanRequest,
    AgentGoalType, ThoughtType
)
from .cognition.cognition import shared_memory
from .orchestrator import orchestrator

class ConductorAgent(Agent):
    """
    The ConductorAgent acts as the central message router for the system.
    It receives user queries and thoughts from other agents and delegates
    the actual execution logic to the Orchestrator. It also handles
    requests to re-plan when a graph execution fails.
    """
    def __init__(self, name: str, seed: str):
        super().__init__(name=name, seed=seed)
        self.on_message(model=AgentRegistration)(self.handle_agent_registration)
        self.on_message(model=Thought)(self.handle_thought)
        self.on_message(model=UserQuery)(self.handle_user_query)
        self.on_message(model=ReplanRequest)(self.handle_replan_request)
        self.on_event("startup")(self.register_self)

    async def register_self(self, ctx: Context):
        """Registers the Conductor with the central registry on startup."""
        agent_registry.register("conductor", self.address)
        ctx.logger.info(f"Conductor registered at {self.address}")

    async def handle_agent_registration(self, ctx: Context, sender: str, msg: AgentRegistration):
        """Handles registration requests from other agents."""
        agent_registry.register(msg.agent_type, sender)

    async def handle_user_query(self, ctx: Context, sender: str, msg: UserQuery):
        """Handles the initial user query by storing it and dispatching a PLAN goal."""
        ctx.logger.info(f"Conductor received user query: '{msg.text}'")
        shared_memory.set(f"{msg.request_id}:query", msg.text)
        await self._request_new_plan(ctx, msg.request_id)

    async def handle_thought(self, ctx: Context, sender: str, msg: Thought):
        """Delegates incoming thoughts to the appropriate handler in the orchestrator."""
        ctx.logger.info(f"Conductor received Thought of type '{msg.type}' from agent {sender}")

        if msg.type == ThoughtType.FAILED:
            await self._handle_failed_thought(ctx, msg)
            return

        if msg.metadata.get("goal_type") == str(AgentGoalType.PLAN):
            await orchestrator.start_new_graph(ctx, msg.request_id, msg.content)
        else:
            node_id = msg.metadata.get("node_id")
            await orchestrator.handle_step_completion(ctx, msg.request_id, node_id, msg.impressions)

    async def handle_replan_request(self, ctx: Context, sender: str, msg: ReplanRequest):
        """Handles a request from the orchestrator to create a new plan."""
        ctx.logger.warning(f"Received replan request for {msg.request_id} due to: {msg.reason}")
        await self._request_new_plan(ctx, msg.request_id)

    async def _request_new_plan(self, ctx: Context, request_id: str):
        """Sends a request to the Planner agent to generate a new graph."""
        original_query = shared_memory.get(f"{request_id}:query")
        if not original_query:
            ctx.logger.error(f"Cannot re-plan for request {request_id}: Original query not found.")
            return

        planner_address = agent_registry.get_agent(AgentType.PLANNER.value)
        if not planner_address:
            ctx.logger.error("Planner agent not found in registry.")
            return

        ctx.logger.info(f"Requesting new plan for request: {request_id}")
        await ctx.send(planner_address, AgentGoal(
            request_id=request_id,
            type=AgentGoalType.PLAN,
            content=original_query
        ))

    async def _handle_failed_thought(self, ctx: Context, msg: Thought):
        """Handles any failed thought by notifying the orchestrator."""
        ctx.logger.error(f"Goal failed for request {request_id}. Content: {msg.content}")
        orchestrator.handle_failure(msg.request_id)

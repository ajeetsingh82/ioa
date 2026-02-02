# This agent is a specialized researcher.
import os
from uagents import Agent, Context
from .models import MissionBrief, WorkerCompletion, AgentRegistration
from .google_search import search_web
from .shared_memory import shared_memory

# We can run multiple instances of this worker.
# The seed will be passed in dynamically when creating the agent.
def create_worker_agent(name: str, seed: str, orchestrator_address: str):
    agent = Agent(name=name, seed=seed)

    @agent.on_event("startup")
    async def register_with_orchestrator(ctx: Context):
        """Registers the worker with the orchestrator on startup."""
        ctx.logger.info(f"Worker {agent.name} starting up and registering...")
        await ctx.send(orchestrator_address, AgentRegistration(agent_name=agent.name, agent_type="worker"))

    @agent.on_message(model=MissionBrief)
    async def handle_mission_brief(ctx: Context, sender: str, msg: MissionBrief):
        """
        Executes the research mission provided by the orchestrator.
        """
        ctx.logger.info(f"Worker {agent.name} received mission: '{msg.sub_task}' with labels {msg.labels}")

        # 1. Autonomous Discovery: Perform web search.
        query = f"{msg.sub_task} {' '.join(msg.labels)}"
        retrieved_text = search_web(query, max_results=3)

        # 2. Semantic Filter & Quality Scoring (Simplified)
        filtered_content = ""
        if any(label.lower() in retrieved_text.lower() for label in msg.labels):
            filtered_content = retrieved_text
            # Store the filtered content in the shared memory, namespaced by labels.
            for label in msg.labels:
                shared_memory.set(f"{msg.request_id}:{label}", filtered_content)
            ctx.logger.info(f"Worker {agent.name} stored content for labels: {msg.labels}")
        else:
            ctx.logger.info(f"Worker {agent.name} found no relevant content for labels.")

        # 3. Notify Orchestrator of completion.
        completion_message = WorkerCompletion(
            request_id=msg.request_id,
            worker_name=agent.name,
            status="Completed",
        )
        await ctx.send(msg.orchestrator_address, completion_message)

    return agent

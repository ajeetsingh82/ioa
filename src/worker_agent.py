# This agent is a specialized researcher.
import os
from uagents import Agent, Context
from .models import MissionBrief, WorkerCompletion, AgentRegistration
from .google_search import search_web
from .shared_memory import shared_memory
from .rag_agent import think

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
        Executes the research mission: search, filter, and store relevant information.
        """
        ctx.logger.info(f"Worker {agent.name} received mission for query: '{msg.query}' with label: {msg.label}")

        # 1. Autonomous Discovery: Perform web search (now gets top 3 results)
        search_query = f"{msg.query} {msg.label}" if msg.label else msg.query
        retrieved_text = search_web(search_query)

        # 2. Semantic Filter: Use LLM to extract relevant information
        if msg.label:
            filter_prompt = f"From the text below, extract all paragraphs and sentences relevant to '{msg.label}'. If no relevant information is found, state that clearly."
            filtered_content = think(context=retrieved_text, goal=filter_prompt)
        else:
            # For the general query, summarize the content in relation to the original question
            filter_prompt = f"Summarize the key points from the following text in relation to the question '{msg.query}'. Focus on providing a comprehensive overview."
            filtered_content = think(context=retrieved_text, goal=filter_prompt)
        
        ctx.logger.info(f"Worker {agent.name} filtered content. Length: {len(filtered_content)}")

        # 3. Write to Memory: Store the filtered content in the shared memory
        namespace = msg.label if msg.label else "general"
        shared_memory.set(f"{msg.request_id}:{namespace}", filtered_content)
        ctx.logger.info(f"Worker {agent.name} stored content for label: {namespace}")

        # 4. Notify Orchestrator of completion
        completion_message = WorkerCompletion(
            request_id=msg.request_id,
            worker_name=agent.name,
            status="Completed",
        )
        await ctx.send(msg.orchestrator_address, completion_message)

    return agent

# This agent will act as the "Brain" of the operation.
import os
import re
from uagents import Agent, Context
from .models import UserQuery, MissionBrief, SynthesisRequest, AgentRegistration, WorkerCompletion, Query
from .rag_agent import think

ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_SEED", "orchestrator_agent_seed")

orchestrator_agent = Agent(
    name="orchestrator_agent",
    port=8001,
    seed=ORCHESTRATOR_SEED,
)

available_workers = set()
synthesis_agent_address = None
mission_status = {}

@orchestrator_agent.on_message(model=AgentRegistration)
async def handle_agent_registration(ctx: Context, sender: str, msg: AgentRegistration):
    """Handles registration messages from worker and synthesis agents."""
    global synthesis_agent_address
    if msg.agent_type == "worker":
        ctx.logger.info(f"Worker '{msg.agent_name}' registered with address: {sender}")
        available_workers.add(sender)
    elif msg.agent_type == "synthesis":
        ctx.logger.info(f"Synthesis agent '{msg.agent_name}' registered with address: {sender}")
        synthesis_agent_address = sender

@orchestrator_agent.on_message(model=UserQuery)
async def handle_user_query(ctx: Context, sender: str, msg: UserQuery):
    """Decomposes the user query, creates missions, and dispatches them to workers."""
    ctx.logger.info(f"Orchestrator received query: '{msg.text}'")
    
    if not available_workers:
        await ctx.send(sender, Query(text="No workers available to handle the request."))
        return
    if not synthesis_agent_address:
        await ctx.send(sender, Query(text="Synthesis agent not available."))
        return

    # 1. Query Impressionism: Generate labels using the LLM
    #prompt = f"Generate 3 specific keywords for the query: '{msg.text}'. Return them as a comma-separated list, each enclosed in double quotes."
    prompt = f"""
        Analyze the user query: '{msg.text}'

        Your goal is to extract 3 distinct, high-level search labels. 
        These labels must be:
        1. Atomic: No full sentences. 1-3 words maximum per label.
        2. Distinct: Each label should cover a different angle of the query (e.g., 'syntax', 'market-demand', 'learning-curve').
        3. Context-Rich: Use terms that help a search engine find technical or factual data.

        Return ONLY a comma-separated list, each enclosed in double quotes.
        Example Output: "keyword1", "keyword2", "keyword3"
        """
    labels_string = think(context="", goal=prompt)
    labels = re.findall(r'"(.*?)"', labels_string)
    ctx.logger.info(f"Generated labels: {labels}")

    # 2. Worker Dispatch
    worker_list = list(available_workers)
    # We have labels + 1 general mission
    total_potential_missions = len(labels) + 1
    num_missions_to_dispatch = min(len(worker_list), total_potential_missions)

    mission_status[msg.request_id] = {
        "total_missions": num_missions_to_dispatch,
        "completed_missions": 0,
        "user_agent_address": sender,
        "original_query": msg.text,
        "labels": labels + ["general"], # Include 'general' for the unlabeled query
    }

    # Dispatch general mission first
    if num_missions_to_dispatch > 0:
        mission = MissionBrief(
            request_id=msg.request_id,
            query=msg.text,
            label=None,
            orchestrator_address=orchestrator_agent.address
        )
        await ctx.send(worker_list[0], mission)
        ctx.logger.info(f"Dispatched general mission to worker {worker_list[0]}")

    # Dispatch labeled missions
    for i in range(1, num_missions_to_dispatch):
        label = labels[i-1]
        mission = MissionBrief(
            request_id=msg.request_id,
            query=msg.text,
            label=label,
            orchestrator_address=orchestrator_agent.address
        )
        await ctx.send(worker_list[i], mission)
        ctx.logger.info(f"Dispatched mission with label '{label}' to worker {worker_list[i]}")

@orchestrator_agent.on_message(model=WorkerCompletion)
async def handle_worker_completion(ctx: Context, sender: str, msg: WorkerCompletion):
    """Tracks mission completion and triggers synthesis when all workers are done."""
    ctx.logger.info(f"Received completion from worker '{msg.worker_name}' for request {msg.request_id}")
    
    if msg.request_id in mission_status:
        mission_status[msg.request_id]["completed_missions"] += 1
        
        if mission_status[msg.request_id]["completed_missions"] >= mission_status[msg.request_id]["total_missions"]:
            ctx.logger.info(f"All workers finished for request {msg.request_id}. Triggering synthesis.")
            
            status = mission_status[msg.request_id]
            synthesis_request = SynthesisRequest(
                request_id=msg.request_id,
                original_query=status["original_query"],
                labels=status["labels"],
                user_agent_address=status["user_agent_address"],
            )
            
            await ctx.send(synthesis_agent_address, synthesis_request)
            del mission_status[msg.request_id]

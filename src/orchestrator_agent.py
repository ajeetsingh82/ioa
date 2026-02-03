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
        await ctx.send(sender, Query(text="No workers available."))
        return
    if not synthesis_agent_address:
        await ctx.send(sender, Query(text="Synthesis agent not available."))
        return

    # 1. The Impressionist Phase: Generate diverse search queries
    prompt = f"""
        Analyze the user query: '{msg.text}'
        Generate 3 diverse and specific search queries that would provide comprehensive context to answer the user's question.
        Return ONLY a comma-separated list of the queries in double quotes.
        Example: "query 1", "query 2", "query 3"
    """
    labels_string = think(context="", goal=prompt)
    labels = re.findall(r'"(.*?)"', labels_string)

    # Always include 'general' to ensure we have a broad baseline
    all_missions = ["general"] + labels
    ctx.logger.info(f"Generated Cognitive Labels: {all_missions}")

    # 2. Strategic Dispatch
    worker_list = list(available_workers)
    num_workers = len(worker_list)

    # We track how many missions we are actually sending out
    missions_to_send = all_missions[:num_workers]

    mission_status[msg.request_id] = {
        "total_missions": len(missions_to_send),
        "completed_missions": 0,
        "user_agent_address": sender,
        "original_query": msg.text,
        "labels": missions_to_send,
    }

    # 3. Distributed Execution
    for i, label in enumerate(missions_to_send):
        target_worker = worker_list[i]

        clean_label = None if label == "general" else label

        mission = MissionBrief(
            request_id=msg.request_id,
            query=msg.text,
            label=clean_label,
            orchestrator_address=orchestrator_agent.address
        )

        await ctx.send(target_worker, mission)
        ctx.logger.info(f"Worker {target_worker} assigned to Knowledge Bucket: '{label}'")

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

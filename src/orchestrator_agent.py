# This agent will act as the "Brain" of the operation.
import os
from uagents import Agent, Context
from .models import UserQuery, MissionBrief, SynthesisRequest, AgentRegistration, WorkerCompletion, Query

ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_SEED", "orchestrator_agent_seed")

orchestrator_agent = Agent(
    name="orchestrator_agent",
    port=8001,
    seed=ORCHESTRATOR_SEED,
)

# A set to store the addresses of registered and available worker agents
available_workers = set()
# Variable to store the address of the synthesis agent
synthesis_agent_address = None
# A dictionary to track the status of dispatched missions
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
    else:
        ctx.logger.warning(f"Unknown agent type '{msg.agent_type}' registered by '{msg.agent_name}'")

@orchestrator_agent.on_message(model=UserQuery)
async def handle_user_query(ctx: Context, sender: str, msg: UserQuery):
    """Decomposes the user query and dispatches missions to available workers."""
    ctx.logger.info(f"Orchestrator received query: '{msg.text}'")
    
    if not available_workers:
        await ctx.send(sender, Query(text="No workers available to handle the request."))
        return
    
    if not synthesis_agent_address:
        await ctx.send(sender, Query(text="Synthesis agent not available. Please ensure it's running."))
        return

    # 1. Query Impressionism (Placeholder LLM call)
    # In a real implementation, an LLM would generate these based on the query.
    labels = ["python", "uagents", "networking"]
    sub_tasks = [
        "Find examples of uAgent communication",
        "Explain how uAgent addresses work",
        "Look for best practices in uAgent networking",
    ]
    
    ctx.logger.info(f"Generated labels: {labels} and sub-tasks: {sub_tasks}")

    # Initialize mission status for this request
    mission_status[msg.request_id] = {
        "total_missions": 0,
        "completed_missions": 0,
        "user_agent_address": sender,
        "original_query": msg.text,
        "labels": labels,
    }

    # 2. Worker Dispatch
    worker_list = list(available_workers)
    mission_count = min(len(worker_list), len(sub_tasks))
    mission_status[msg.request_id]["total_missions"] = mission_count

    for i in range(mission_count):
        worker_address = worker_list[i]
        mission = MissionBrief(
            request_id=msg.request_id,
            sub_task=sub_tasks[i],
            labels=labels,
            orchestrator_address=orchestrator_agent.address,
        )
        await ctx.send(worker_address, mission)
        ctx.logger.info(f"Dispatched mission '{sub_tasks[i]}' to worker {i+1}")

@orchestrator_agent.on_message(model=WorkerCompletion)
async def handle_worker_completion(ctx: Context, sender: str, msg: WorkerCompletion):
    """Tracks mission completion and triggers synthesis when all workers are done."""
    ctx.logger.info(f"Received completion from worker '{msg.worker_name}' for request {msg.request_id}")
    
    if msg.request_id in mission_status:
        mission_status[msg.request_id]["completed_missions"] += 1
        
        # Check if all dispatched missions for this request are complete
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
            
            # Clean up the mission status for this request
            del mission_status[msg.request_id]

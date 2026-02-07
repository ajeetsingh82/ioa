import os
import threading
import uvicorn
import logging

from uagents import Bureau, Agent, Context

from src.agent_registry import agent_registry
from src.pipeline import pipeline_manager
from src.model.models import (
    AgentRegistration, UserQuery, NewPipeline,
    ScoutRequest, ScoutResponse,
    FilterRequest, TaskCompletion,
    ArchitectRequest, ArchitectResponse
)

# --- Agent Imports ---
from src.agents.gateway import gateway
from src.agents.strategist import StrategistAgent
from src.agents.scout import ScoutAgent
from src.agents.filter import FilterAgent
from src.agents.architect import ArchitectAgent
from src.agents.program_of_thought import ProgramOfThoughtAgent

# HTTP gateway imports
from gateway_http import create_app

# ============================================================
# Agent Initialization
# ============================================================
DEPTH = 10
def init_agents():
    conductor = Agent(name="conductor", seed="conductor_seed")

    strategist = StrategistAgent(
        name="strategist",
        seed="strategist_seed",
        conductor_address=conductor.address,
    )

    scouts = [
        ScoutAgent(
            name=f"scout_{i}",
            seed=f"scout_seed_{i}",
            conductor_address=conductor.address,
        )
        for i in range(DEPTH)
    ]

    filters = [
        FilterAgent(
            name=f"filter_{i}",
            seed=f"filter_seed_{i}",
            conductor_address=conductor.address,
        )
        for i in range(DEPTH)
    ]

    architect = ArchitectAgent(
        name="architect",
        seed="architect_seed",
        conductor_address=conductor.address,
    )

    program_of_thought = ProgramOfThoughtAgent(
        name="program_of_thought",
        seed="program_of_thought_seed",
        conductor_address=conductor.address,
    )

    # Configure gateway
    gateway.strategist_address = strategist.address
    gateway._conductor_address = conductor.address # Manually set conductor address for BaseAgent registration

    return conductor, strategist, scouts, filters, architect, program_of_thought


# ============================================================
# Conductor Handlers
# ============================================================

def register_conductor_handlers(conductor: Agent):
    @conductor.on_message(model=AgentRegistration)
    async def handle_agent_registration(ctx: Context, sender: str, msg: AgentRegistration):
        # This log is now handled by the agent registry itself at DEBUG level
        agent_registry.register(msg.agent_type, sender)

    @conductor.on_message(model=NewPipeline)
    async def on_new_pipeline(ctx: Context, sender: str, msg: NewPipeline):
        await process_pipeline_step(ctx, msg.request_id)

    @conductor.on_message(model=ScoutResponse)
    async def handle_scout_response(ctx: Context, sender: str, msg: ScoutResponse):
        agent_registry.release_agent("scout", sender)
        filter_addr = agent_registry.lease_agent("filter")
        if filter_addr:
            pipeline = await pipeline_manager.get_pipeline(msg.request_id)
            if pipeline:
                gateway.remember_query(msg.request_id, pipeline.original_query)
                await ctx.send(
                    filter_addr,
                    FilterRequest(
                        request_id=msg.request_id,
                        content=msg.content,
                        label=pipeline.all_labels[0] if pipeline.all_labels else "general", # Use the first label for now
                        original_query=pipeline.original_query,
                    ),
                )
        else:
            ctx.logger.warning("No Filter agents available")
        await process_pipeline_step(ctx, msg.request_id)

    @conductor.on_message(model=TaskCompletion)
    async def handle_task_completion(ctx: Context, sender: str, msg: TaskCompletion):
        agent_registry.release_agent("filter", sender)
        pipeline = await pipeline_manager.get_pipeline(msg.request_id)
        if pipeline:
            pipeline.complete_task()
            if pipeline.is_complete():
                await trigger_architect(ctx, pipeline)

    @conductor.on_message(model=ArchitectResponse)
    async def handle_architect_response(ctx: Context, sender: str, msg: ArchitectResponse):
        agent_registry.release_agent("architect", sender)
        await ctx.send(gateway.address, msg)
        await pipeline_manager.remove_pipeline(msg.request_id)


# ============================================================
# Pipeline Helpers
# ============================================================

async def process_pipeline_step(ctx: Context, request_id: str):
    pipeline = await pipeline_manager.get_pipeline(request_id)
    if pipeline and pipeline.has_pending_scout_tasks():
        scout_addr = agent_registry.lease_agent("scout")
        if scout_addr:
            task = pipeline.get_next_scout_task()
            await ctx.send(
                scout_addr,
                ScoutRequest(
                    request_id=pipeline.request_id,
                    sub_query=task["sub_query"],
                    label=task["label"],
                ),
            )


async def trigger_architect(ctx: Context, pipeline):
    architect_addr = agent_registry.lease_agent("architect")
    if architect_addr:
        await ctx.send(
            architect_addr,
            ArchitectRequest(
                request_id=pipeline.request_id,
                original_query=pipeline.original_query,
                labels=pipeline.all_labels,
            ),
        )
    else:
        ctx.logger.warning("Architect agent not available")


# ============================================================
# HTTP Server
# ============================================================

gateway_http_host = "127.0.0.1"
gateway_http_port = 9000


def run_gateway_http():
    app = create_app(gateway.queue)
    uvicorn.run(
        app,
        host=gateway_http_host,
        port=gateway_http_port,
        log_level="info",
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    # Configure root logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("Main")

    # Suppress 'primp' logger INFO messages
    logging.getLogger("primp").setLevel(logging.WARNING)

    # Set environment variables for UserProxy / UI
    os.environ["GATEWAY_ADDRESS"] = f"http://{gateway_http_host}:{gateway_http_port}/submit"
    os.environ["CHAT_SERVER_URL"] = "http://127.0.0.1:8080/api/result"

    # Initialize agents
    conductor, strategist, scouts, filters, architect, program_of_thought = init_agents()

    # Register conductor handlers
    register_conductor_handlers(conductor)

    # Create Bureau
    bureau = Bureau(port=8000)
    bureau.add(conductor)
    bureau.add(gateway)
    bureau.add(strategist)
    bureau.add(architect)
    bureau.add(program_of_thought)

    for agent in scouts:
        bureau.add(agent)
    for agent in filters:
        bureau.add(agent)

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_gateway_http, daemon=True)
    http_thread.start()

    logger.info(f"Gateway HTTP running on http://{gateway_http_host}:{gateway_http_port}")
    logger.info("Starting Agent Bureau on port 8000...")

    # Start Bureau (blocking call)
    bureau.run()

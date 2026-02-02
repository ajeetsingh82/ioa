# This agent is the final "Editor."
import os
from uagents import Agent, Context
from .models import SynthesisRequest, Query, AgentRegistration
from .shared_memory import shared_memory
from .rag_agent import think

SYNTHESIS_SEED = os.getenv("SYNTHESIS_SEED", "synthesis_agent_seed")

def create_synthesis_agent(orchestrator_address: str):
    agent = Agent(
        name="synthesis_agent",
        port=8003,
        seed=SYNTHESIS_SEED,
    )

    @agent.on_event("startup")
    async def register_with_orchestrator(ctx: Context):
        """Registers the synthesis agent with the orchestrator on startup."""
        ctx.logger.info(f"Synthesis agent starting up and registering...")
        await ctx.send(orchestrator_address, AgentRegistration(agent_name=agent.name, agent_type="synthesis"))

    @agent.on_message(model=SynthesisRequest)
    async def handle_synthesis_request(ctx: Context, sender: str, msg: SynthesisRequest):
        """
        Assembles the final answer from the data in shared memory.
        """
        ctx.logger.info(f"Synthesis agent received request for: '{msg.original_query}'")

        # 1. Targeted Retrieval: Query the shared memory for relevant buckets.
        context = ""
        for label in msg.labels:
            retrieved_data = shared_memory.get(f"{msg.request_id}:{label}")
            if retrieved_data:
                context += f"--- Content for label '{label}' ---\n{retrieved_data}\n\n"
        
        if not context:
            final_answer = "Could not retrieve any relevant information from the workers."
        else:
            # 2. Grounded Generation: Use the LLM to generate the final response.
            final_answer = think(context=context, goal=msg.original_query)

        # 3. Send the final answer back to the user agent.
        await ctx.send(msg.user_agent_address, Query(text=final_answer))
        ctx.logger.info("Synthesis complete. Final answer sent to user agent.")

        # 4. Ephemeral State: Clean up the shared memory for this request.
        for label in msg.labels:
            shared_memory.delete(f"{msg.request_id}:{label}")
        ctx.logger.info(f"Cleaned up shared memory for request_id: {msg.request_id}")
    
    return agent

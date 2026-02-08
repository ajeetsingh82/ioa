from uagents import Agent, Context

from agents.filter import AGENT_TYPE_FILTER
from .agent_registry import agent_registry
from .pipeline import pipeline_manager
from .model.models import (
    AgentRegistration, NewPipeline, Thought
)
from .agents.gateway import gateway
from .utils.utils import to_msg_type

class ConductorAgent(Agent):
    def __init__(self, name: str, seed: str):
        super().__init__(name=name, seed=seed)
        self.on_message(model=AgentRegistration)(self.handle_agent_registration)
        self.on_message(model=NewPipeline)(self.on_new_pipeline)
        self.on_message(model=Thought)(self.handle_thought)

    async def handle_agent_registration(self, ctx: Context, sender: str, msg: AgentRegistration):
        agent_registry.register(msg.agent_type, sender)

    async def on_new_pipeline(self, ctx: Context, sender: str, msg: NewPipeline):
        await self.process_pipeline_step(ctx, msg.request_id)

    async def handle_thought(self, ctx: Context, sender: str, msg: Thought):
        """
        Handles all cognitive messages and routes them based on type.
        """
        sender_type = agent_registry.get_agent_type(sender)
        if sender_type:
            sender_type = sender_type.upper()
            
        ctx.logger.info(f"Conductor received Thought of type '{msg.type}' from a {sender_type} agent.")

        # Release the agent
        if sender_type:
            agent_registry.release_agent(sender_type, sender)

        # If it's a response from Architect, forward to Gateway
        if msg.type == "RESPONSE":
             await ctx.send(gateway.address, msg)
             await pipeline_manager.remove_pipeline(msg.request_id)
             return

        # Identify the step that completed
        step_id = msg.metadata.get("step_id")
        if step_id:
            pipeline = await pipeline_manager.get_pipeline(msg.request_id)
            if pipeline:
                pipeline.mark_step_complete(step_id, msg.content)
                
                # Special handling for RETRIEVE -> Gateway memory (legacy requirement?)
                # If we want to keep the "remember query" logic, we can do it here if needed.
                # But the new pipeline flow handles data passing via step results.
                
                await self.process_pipeline_step(ctx, msg.request_id)
        else:
            ctx.logger.warning(f"Received message without step_id from {sender_type}")

    async def process_pipeline_step(self, ctx: Context, request_id: str):
        pipeline = await pipeline_manager.get_pipeline(request_id)
        if not pipeline:
            return

        executable_steps = pipeline.get_executable_steps()
        for step in executable_steps:
            agent_addr = agent_registry.lease_agent(step.agent_type)
            if agent_addr:
                # Resolve content if needed
                content = step.content
                if step.agent_type == AGENT_TYPE_FILTER:
                    # Filter expects content from the previous step (Retrieve)
                    if step.dependencies:
                        dep_id = step.dependencies[0]
                        content = pipeline.results.get(dep_id, "")
                
                # Prepare metadata
                metadata = step.metadata.copy()
                metadata["step_id"] = step.id
                
                # Determine message type
                msg_type = to_msg_type(step.agent_type)
                
                pipeline.mark_step_running(step.id)
                
                await ctx.send(
                    agent_addr,
                    Thought(
                        request_id=pipeline.request_id,
                        type=msg_type,
                        content=content,
                        metadata=metadata
                    )
                )
            else:
                ctx.logger.warning(f"No agents available for type {step.agent_type}")

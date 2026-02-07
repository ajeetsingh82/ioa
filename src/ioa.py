from uagents import Agent, Context
from .agent_registry import agent_registry
from .pipeline import pipeline_manager
from .model.models import (
    AgentRegistration, NewPipeline, CognitiveMessage
)
from .agents.gateway import gateway
from .agents.scout import AGENT_TYPE_RETRIEVE
from .agents.filter import AGENT_TYPE_FILTER
from .agents.architect import AGENT_TYPE_SYNTHESIZE

class ConductorAgent(Agent):
    def __init__(self, name: str, seed: str):
        super().__init__(name=name, seed=seed)
        self.on_message(model=AgentRegistration)(self.handle_agent_registration)
        self.on_message(model=NewPipeline)(self.on_new_pipeline)
        self.on_message(model=CognitiveMessage)(self.handle_cognitive_message)

    async def handle_agent_registration(self, ctx: Context, sender: str, msg: AgentRegistration):
        agent_registry.register(msg.agent_type, sender)

    async def on_new_pipeline(self, ctx: Context, sender: str, msg: NewPipeline):
        await self.process_pipeline_step(ctx, msg.request_id)

    async def handle_cognitive_message(self, ctx: Context, sender: str, msg: CognitiveMessage):
        """
        Handles all cognitive messages and routes them based on type.
        """
        sender_type = agent_registry.get_agent_type(sender)
        if sender_type:
            sender_type = sender_type.upper()
            
        ctx.logger.info(f"Conductor received CognitiveMessage of type '{msg.type}' from a {sender_type} agent.")

        if sender_type == AGENT_TYPE_RETRIEVE: # Response from Scout
            agent_registry.release_agent(AGENT_TYPE_RETRIEVE, sender)
            filter_addr = agent_registry.lease_agent(AGENT_TYPE_FILTER)
            if filter_addr:
                pipeline = await pipeline_manager.get_pipeline(msg.request_id)
                if pipeline:
                    gateway.remember_query(msg.request_id, pipeline.original_query)
                    await ctx.send(
                        filter_addr,
                        CognitiveMessage(
                            request_id=msg.request_id,
                            type="FILTER",
                            content=msg.content,
                            metadata={
                                "label": msg.metadata.get("label", "general"),
                                "original_query": pipeline.original_query
                            }
                        )
                    )
            else:
                ctx.logger.warning("No Filter agents available")
            await self.process_pipeline_step(ctx, msg.request_id)

        elif sender_type == AGENT_TYPE_FILTER: # Response from Filter
            agent_registry.release_agent(AGENT_TYPE_FILTER, sender)
            pipeline = await pipeline_manager.get_pipeline(msg.request_id)
            if pipeline:
                pipeline.complete_task()
                if pipeline.is_complete():
                    await self.trigger_architect(ctx, pipeline)

        elif sender_type == AGENT_TYPE_SYNTHESIZE: # Response from Architect
            agent_registry.release_agent(AGENT_TYPE_SYNTHESIZE, sender)
            await ctx.send(gateway.address, msg)
            await pipeline_manager.remove_pipeline(msg.request_id)
        
        # Add more routing logic here for other types like COMPUTE, etc.

    async def process_pipeline_step(self, ctx: Context, request_id: str):
        pipeline = await pipeline_manager.get_pipeline(request_id)
        if pipeline and pipeline.has_pending_scout_tasks():
            scout_addr = agent_registry.lease_agent(AGENT_TYPE_RETRIEVE)
            if scout_addr:
                task = pipeline.get_next_scout_task()
                await ctx.send(
                    scout_addr,
                    CognitiveMessage(
                        request_id=pipeline.request_id,
                        type="SEARCH",
                        content=task["sub_query"],
                        metadata={"label": task["label"]}
                    )
                )

    async def trigger_architect(self, ctx: Context, pipeline):
        architect_addr = agent_registry.lease_agent(AGENT_TYPE_SYNTHESIZE)
        if architect_addr:
            # Convert list of labels to comma-separated string for metadata
            labels_str = ",".join(pipeline.all_labels)
            await ctx.send(
                architect_addr,
                CognitiveMessage(
                    request_id=pipeline.request_id,
                    type="SYNTHESIZE",
                    content="", # Content is empty as Architect pulls from shared memory
                    metadata={
                        "original_query": pipeline.original_query,
                        "labels": labels_str
                    }
                )
            )
        else:
            ctx.logger.warning("Architect agent not available")

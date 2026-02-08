# The Strategist Agent: The "Brain" of the operation.
from uagents import Context
from .base import BaseAgent
from ..model.models import UserQuery, NewPipeline
from ..pipeline import pipeline_manager, PipelineStep
from ..utils.json_parser import SafeJSONParser
from .scout import AGENT_TYPE_RETRIEVE
from .filter import AGENT_TYPE_FILTER
from .architect import AGENT_TYPE_SYNTHESIZE
from ..config.store import agent_config_store

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_STRATEGIST = "strategist"

class StrategistAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_STRATEGIST
        
        # Load configuration from the central store with an exact match
        config = agent_config_store.get_config(self.type)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type}' not found.")
        self.legacy_prompt = config.get_prompt('legacy')
        if not self.legacy_prompt:
            raise ValueError(f"Prompt 'legacy' not found for agent type '{self.type}'.")
        
        self.on_message(model=UserQuery)(self.handle_user_query)

    async def handle_user_query(self, ctx: Context, sender: str, msg: UserQuery):
        """
        Decomposes the user query into a structured pipeline of tasks.
        """
        ctx.logger.debug(f"Strategist received query: '{msg.text}'")
        
        prompt = self.legacy_prompt.format(query=msg.text)
        
        llm_response = await self.think(context="", goal=prompt)
        tasks_data = json_parser.parse(llm_response)

        if isinstance(tasks_data.get("answer"), list):
             tasks = tasks_data["answer"]
        elif isinstance(tasks_data, list):
            tasks = tasks_data
        else:
            ctx.logger.error(f"Strategist failed to produce a valid task list. Creating a single general task. Raw response: {llm_response}")
            tasks = [{"label": "general", "sub_query": msg.text}]

        # Clean up labels
        for task in tasks:
            if 'label' in task and isinstance(task['label'], str):
                task['label'] = task['label'].strip('., ')

        # Create the pipeline
        pipeline = await pipeline_manager.create_pipeline(msg.request_id, msg.text)
        
        filter_step_ids = []
        all_labels = []

        for task in tasks:
            label = task.get("label", "general")
            sub_query = task.get("sub_query", msg.text)
            all_labels.append(label)

            # Step 1: SCOUT
            scout_step = PipelineStep(
                agent_type=AGENT_TYPE_RETRIEVE,
                content=sub_query,
                metadata={"label": label}
            )
            pipeline.add_step(scout_step)

            # Step 2: FILTER (depends on SCOUT)
            filter_step = PipelineStep(
                agent_type=AGENT_TYPE_FILTER,
                content="", 
                metadata={"label": label, "original_query": msg.text},
                dependencies=[scout_step.id]
            )
            pipeline.add_step(filter_step)
            filter_step_ids.append(filter_step.id)

        # Step 3: ARCHITECT (depends on all FILTER steps)
        architect_step = PipelineStep(
            agent_type=AGENT_TYPE_SYNTHESIZE,
            content="", 
            metadata={"original_query": msg.text, "labels": ",".join(all_labels)},
            dependencies=filter_step_ids
        )
        pipeline.add_step(architect_step)

        ctx.logger.info(f"Created pipeline for request {msg.request_id} with {len(pipeline.steps)} steps.")
        
        await ctx.send(self._conductor_address, NewPipeline(request_id=msg.request_id))

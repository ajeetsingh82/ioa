# The Strategist Agent: The "Brain" of the operation.
from uagents import Context
from .base import BaseAgent
from ..model.models import UserQuery, NewPipeline
from ..pipeline import pipeline_manager, PipelineStep
from ..prompt.prompt import STRATEGIST_PROMPT
from ..utils.json_parser import SafeJSONParser
from .scout import AGENT_TYPE_RETRIEVE
from .filter import AGENT_TYPE_FILTER
from .architect import AGENT_TYPE_SYNTHESIZE

# Instantiate the parser
json_parser = SafeJSONParser()

AGENT_TYPE_PLANNER = "PLANNER"

class StrategistAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_PLANNER
        self.on_message(model=UserQuery)(self.handle_user_query)

    async def handle_user_query(self, ctx: Context, sender: str, msg: UserQuery):
        """
        Decomposes the user query into a structured pipeline of tasks.
        """
        ctx.logger.debug(f"Strategist received query: '{msg.text}'")
        
        prompt = STRATEGIST_PROMPT.format(query=msg.text)
        
        llm_response = await self.think(context="", goal=prompt)
        tasks_data = json_parser.parse(llm_response)

        # The parser guarantees a dict. We need to check if the content is a list.
        # The fallback {"answer": ...} will fail this check.
        if isinstance(tasks_data.get("answer"), list):
             tasks = tasks_data["answer"]
        elif isinstance(tasks_data, list): # The parser might return a list directly
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

            # Step 1: RETRIEVE
            retrieve_step = PipelineStep(
                agent_type=AGENT_TYPE_RETRIEVE,
                content=sub_query,
                metadata={"label": label}
            )
            pipeline.add_step(retrieve_step)

            # Step 2: FILTER (depends on RETRIEVE)
            filter_step = PipelineStep(
                agent_type=AGENT_TYPE_FILTER,
                content="", # Content will be filled by the result of the previous step
                metadata={"label": label, "original_query": msg.text},
                dependencies=[retrieve_step.id]
            )
            pipeline.add_step(filter_step)
            filter_step_ids.append(filter_step.id)

        # Step 3: SYNTHESIZE (depends on all FILTER steps)
        synthesize_step = PipelineStep(
            agent_type=AGENT_TYPE_SYNTHESIZE,
            content="", # Content will be filled by shared memory or results
            metadata={"original_query": msg.text, "labels": ",".join(all_labels)},
            dependencies=filter_step_ids
        )
        pipeline.add_step(synthesize_step)

        ctx.logger.info(f"Created pipeline for request {msg.request_id} with {len(pipeline.steps)} steps.")
        
        await ctx.send(self._conductor_address, NewPipeline(request_id=msg.request_id))

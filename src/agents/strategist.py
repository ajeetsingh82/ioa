# The Strategist Agent: The "Brain" of the operation.
from uagents import Context
from .base import BaseAgent
from ..model.models import UserQuery, NewPipeline
from ..pipeline import pipeline_manager
from ..prompt.prompt import STRATEGIST_PROMPT
from ..utils.json_parser import SafeJSONParser

# Instantiate the parser
json_parser = SafeJSONParser()

class StrategistAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "strategist"
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

        await pipeline_manager.create_pipeline(msg.request_id, tasks, sender, msg.text)
        ctx.logger.info(f"Created pipeline for request {msg.request_id} with {len(tasks)} tasks.")
        
        await ctx.send(self._conductor_address, NewPipeline(request_id=msg.request_id))

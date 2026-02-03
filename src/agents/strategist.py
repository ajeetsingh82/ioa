# The Strategist Agent: The "Brain" of the operation.
import json
from uagents import Context
from .base import BaseAgent
from ..model.models import UserQuery, NewPipeline
from ..pipeline import pipeline_manager
from ..prompt.prompt import STRATEGIST_PROMPT

class StrategistAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self._agent_type = "strategist"
        self.on_message(model=UserQuery)(self.handle_user_query)

    async def handle_user_query(self, ctx: Context, sender: str, msg: UserQuery):
        """
        Decomposes the user query into a structured pipeline of tasks.
        """
        ctx.logger.info(f"Strategist received query: '{msg.text}'")

        prompt = STRATEGIST_PROMPT.format(query=msg.text)
        try:
            tasks_json_string = await self.think(context="", goal=prompt)
            tasks_data = json.loads(tasks_json_string)

            # Ensure tasks are in the correct format
            if isinstance(tasks_data, list) and all(isinstance(item, str) for item in tasks_data):
                tasks = [{"label": item, "sub_query": ""} for item in tasks_data]
            elif isinstance(tasks_data, list) and all(isinstance(item, dict) for item in tasks_data):
                tasks = tasks_data
            else:
                raise TypeError("LLM returned an unexpected format for tasks.")

            for task in tasks:
                if 'label' in task and isinstance(task['label'], str):
                    task['label'] = task['label'].strip('., ')
        except (json.JSONDecodeError, TypeError) as e:
            ctx.logger.warning(f"LLM failed to return valid JSON or format: {e}. Creating a single general task.")
            tasks = [{"label": "general", "sub_query": msg.text}]

        # The sender is now the Gateway, but the user's identity for the response
        # needs to be handled differently. For now, we pass the gateway address.
        # A more robust solution would involve session IDs.
        pipeline_manager.create_pipeline(msg.request_id, tasks, sender, msg.text)
        ctx.logger.info(f"Created pipeline for request {msg.request_id} with {len(tasks)} tasks.")
        
        await ctx.send(self._conductor_address, NewPipeline(request_id=msg.request_id))

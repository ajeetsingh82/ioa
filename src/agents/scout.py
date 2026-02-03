# The Scout Agent: The "Data Hunter"
from uagents import Agent, Context
from ..model.models import AgentRegistration, ScoutRequest, ScoutResponse
from ..data.fetcher import search_web

class ScoutAgent(Agent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed)
        self._agent_type = "scout"
        self._conductor_address = conductor_address
        self.on_event("startup")(self.register_on_startup)
        self.on_message(model=ScoutRequest)(self.search)

    async def register_on_startup(self, ctx: Context):
        """Registers the scout with the Conductor on startup."""
        ctx.logger.info(f"Registering {self._agent_type} agent with Conductor.")
        await ctx.send(self._conductor_address, AgentRegistration(agent_type=self._agent_type))

    async def search(self, ctx: Context, sender: str, msg: ScoutRequest):
        """
        Performs a web search based on the sub-query and returns the raw content.
        """
        ctx.logger.info(f"Scout received request: '{msg.sub_query}'")
        
        content = search_web(msg.sub_query)
        
        await ctx.send(sender, ScoutResponse(
            request_id=msg.request_id,
            content=content,
            label=msg.label
        ))

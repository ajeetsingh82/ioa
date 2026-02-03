# The Gateway Agent: A pure messaging agent that forwards queries.
from uagents import Agent, Context
from ..model.models import UserQuery

# This is a standalone agent instance.
gateway = Agent(
    name="gateway",
    seed="gateway_seed",
)

# This address will be configured from app.py after the strategist is created.
gateway.strategist_address = None 

@gateway.on_message(model=UserQuery)
async def handle_user_query(ctx: Context, sender: str, msg: UserQuery):
    """
    Receives a UserQuery from the external server and forwards it to the Strategist.
    """
    if gateway.strategist_address:
        ctx.logger.info(f"Gateway forwarding query {msg.request_id} to Strategist.")
        await ctx.send(gateway.strategist_address, msg)
    else:
        ctx.logger.error("Strategist address not set on Gateway!")

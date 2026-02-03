from uagents import Agent, Context
from queue import Queue

gateway = Agent(
    name="gateway",
    seed="gateway_seed",
)

gateway.strategist_address = None
gateway.queue = Queue()


@gateway.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("Gateway started")


@gateway.on_interval(period=0.5)
async def process_queue(ctx: Context):
    while not gateway.queue.empty():
        msg = gateway.queue.get()

        if gateway.strategist_address:
            await ctx.send(gateway.strategist_address, msg)
        else:
            ctx.logger.error("Strategist address not configured")

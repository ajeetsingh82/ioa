import requests
from uagents import Agent, Context, Model

# --- 1. THE SCHEMA ---
class Request(Model):
    text: str

# --- 2. THE CAMERA AGENT ---
camera = Agent(
    name="camera",
    port=8000,
    seed="camera_seed",
    endpoint=["http://127.0.0.1:8000/submit"]
)

@camera.on_event("startup")
async def introduce(ctx: Context):
    ctx.logger.info(f"Camera Online at address: {camera.address}")

# --- 3. THE HANDLER ---
@camera.on_message(model=Request)
async def handle_message(ctx: Context, sender: str, msg: Request):
    ctx.logger.info(f"RECEIVED FROM MIC: {msg.text}")

    # Optional: Reply back to the Mic
    # The Mic is on port 8001
    reply_text = "Camera here. Sync acknowledged. Ready for recording."
    await ctx.send(sender, Request(text=reply_text))

if __name__ == "__main__":
    camera.run()
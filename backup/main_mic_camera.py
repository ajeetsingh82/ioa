import requests
from uagents import Agent, Context, Model, Bureau

# --- 1. SHARED SCHEMA ---
class Request(Model):
    text: str

# --- 2. DECOUPLED BRAINS ---
def ask_local_llm(persona_prompt, user_input):
    url = "http://localhost:11434/api/generate"
    # We explicitly inject a unique identity for every single call
    payload = {
        "model": "llama3.2:1b",
        "prompt": f"IDENTITY: {persona_prompt}\n\nINPUT: {user_input}\n\nRESPONSE:",
        "stream": False
    }
    try:
        return requests.post(url, json=payload, timeout=10).json().get('response', "...")
    except:
        return "Brain offline."

# --- 3. THE AGENTS ---
camera = Agent(name="camera", port=8000, seed="camera_recovery")
mic = Agent(name="mic", port=8001, seed="mic_recovery")

# --- 4. UNIQUE PERSONAS ---
MIC_PERSONA = "You are a Mic Agent. You care about 48kHz audio, low floor noise, and perfect sync. You are slightly impatient."
CAMERA_PERSONA = "You are a Camera Agent. You care about 4K resolution, 24fps, and ISO settings. You are very formal and precise."

# --- 5. BEHAVIORS ---

@mic.on_interval(period=15.0)
async def mic_negotiate(ctx: Context):
    # The Mic initiates based on ITS specific persona
    thought = ask_local_llm(MIC_PERSONA, "Ask the camera if it is ready for a 48kHz sync check.")
    ctx.logger.info(f"MIC (Audio): {thought}")
    await ctx.send(camera.address, Request(text=thought))

@camera.on_message(model=Request)
async def camera_logic(ctx: Context, sender: str, msg: Request):
    # The Camera processes the Mic's message through ITS specific persona
    ctx.logger.info(f"CAMERA RECEIVED: {msg.text}")

    response_task = f"The Mic agent just said: '{msg.text}'. Respond to them based on your settings (4K, 24fps)."
    reply = ask_local_llm(CAMERA_PERSONA, response_task)

    await ctx.send(sender, Request(text=reply))

@mic.on_message(model=Request)
async def mic_logic(ctx: Context, sender: str, msg: Request):
    ctx.logger.info(f"MIC RECEIVED FROM CAMERA: {msg.text}")

if __name__ == "__main__":
    bureau = Bureau(port=8000, endpoint=["http://127.0.0.1:8000/submit"])
    bureau.add(camera)
    bureau.add(mic)
    bureau.run()
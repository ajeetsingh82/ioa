import requests
from uagents import Agent, Context, Model

class Request(Model):
    text: str

def ask_local_llm(system_prompt, user_input):
    url = "http://localhost:11434/api/generate"
    payload = {"model": "llama3.2:1b", "prompt": f"{system_prompt}\n{user_input}", "stream": False}
    try:
        return requests.post(url, json=payload).json().get('response', "...")
    except:
        return "Ollama not running."

# Target info
CAMERA_URL = "http://127.0.0.1:8000/submit"

mic = Agent(name="mic", port=8001, seed="mic_secret", endpoint=["http://127.0.0.1:8001/submit"])

@mic.on_interval(period=15.0)
async def check_sync(ctx: Context):
    thought = ask_local_llm("You are a Mic Avatar.", "Request a sync check.")
    ctx.logger.info(f"Mic Thinking: {thought}")

    # DIRECT HTTP POST: This bypasses the 'Unable to resolve' error entirely
    # We send the message exactly how the camera expects it
    payload = {
        "sender": str(mic.address),
        "target": "agent1qf0p3gpv8z0t2efd3m9vqr2t0rx0e8s4l3fk59dne2hn6445uj4p6atzewc",
        "model": "Request",
        "protocol": "1.0",
        "payload": {"text": thought}
    }

    try:
        requests.post(CAMERA_URL, json=payload)
        ctx.logger.info("Direct Link Established: Message delivered to Camera.")
    except Exception as e:
        ctx.logger.error(f"Camera unreachable: {e}")

@mic.on_message(model=Request)
async def handle_reply(ctx: Context, sender: str, msg: Request):
    ctx.logger.info(f"Reply: {msg.text}")

if __name__ == "__main__":
    mic.run()
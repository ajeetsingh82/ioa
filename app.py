import threading, queue, time, os
from uagents import Agent, Context, Bureau
from src.models import Query
from src.rag_agent import rag_agent

# This agent represents the user interface
user_agent = Agent(name="user_agent", port=8002, seed="user_agent_seed")
user_input_queue = queue.Queue()

@user_agent.on_interval(period=1.0)
async def send_query_to_rag(ctx: Context):
    """Checks for user input and sends it to the RAG agent."""
    try:
        query_text = user_input_queue.get_nowait()
        await ctx.send(rag_agent.address, Query(text=query_text))
    except queue.Empty:
        pass

@user_agent.on_message(model=Query)
async def display_response(ctx: Context, sender: str, msg: Query):
    """Receives the final answer from the RAG agent and displays it."""
    print(f"\n[RAG Response]: {msg.text}")
    print(">> ", end="", flush=True)

def console():
    """A simple console loop to capture user input."""
    time.sleep(2)
    print("\n--- RAG Agent Test Environment ---")
    print("Ask any question. The RAG agent will search Google and use an LLM to answer.")
    print("Type 'exit' or 'quit' to stop.")
    while True:
        msg = input(">> ")
        if msg.lower() in ['exit', 'quit']:
            os._exit(0)
        user_input_queue.put(msg)

if __name__ == "__main__":
    bureau = Bureau()
    bureau.add(rag_agent)
    bureau.add(user_agent)

    # Start the console input thread
    threading.Thread(target=console, daemon=True).start()
    
    # Run the agent bureau
    bureau.run()
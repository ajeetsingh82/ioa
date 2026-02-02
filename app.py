import threading, queue, time, os
from uagents import Agent, Context, Bureau
from src.models import Query, UserQuery
from src.orchestrator_agent import orchestrator_agent
from src.worker_agent import create_worker_agent
from src.synthesis_agent import create_synthesis_agent

# This agent represents the user interface
user_agent = Agent(name="user_agent", port=8002, seed="user_agent_seed")
user_input_queue = queue.Queue()

@user_agent.on_interval(period=1.0)
async def send_query_to_orchestrator(ctx: Context):
    """Checks for user input and sends it to the Orchestrator agent."""
    try:
        query_text = user_input_queue.get_nowait()
        # Send UserQuery to the orchestrator
        await ctx.send(orchestrator_agent.address, UserQuery(text=query_text))
    except queue.Empty:
        pass

@user_agent.on_message(model=Query)
async def display_response(ctx: Context, sender: str, msg: Query):
    """Receives the final answer from the Synthesis agent and displays it."""
    print(f"\n[RAG Response]: {msg.text}")
    print(">> ", end="", flush=True)

def console():
    """A simple console loop to capture user input."""
    time.sleep(2)
    print("\n--- Distributed RAG Network ---")
    print("Ask any question. The Orchestrator will dispatch workers to research and the Synthesis agent will answer.")
    print("Type 'exit' or 'quit' to stop.")
    while True:
        msg = input(">> ")
        if msg.lower() in ['exit', 'quit']:
            os._exit(0)
        user_input_queue.put(msg)

if __name__ == "__main__":
    # Get the orchestrator address
    orchestrator_address = orchestrator_agent.address
    print(f"Orchestrator Address: {orchestrator_address}")

    # Create the Synthesis Agent
    synthesis_agent = create_synthesis_agent(orchestrator_address)
    
    # Create Worker Agents
    worker1 = create_worker_agent("worker_1", "worker_1_seed", orchestrator_address)
    worker2 = create_worker_agent("worker_2", "worker_2_seed", orchestrator_address)
    worker3 = create_worker_agent("worker_3", "worker_3_seed", orchestrator_address)

    bureau = Bureau()
    bureau.add(orchestrator_agent)
    bureau.add(synthesis_agent)
    bureau.add(worker1)
    bureau.add(worker2)
    bureau.add(worker3)
    bureau.add(user_agent)

    # Start the console input thread
    threading.Thread(target=console, daemon=True).start()
    
    # Run the agent bureau
    bureau.run()
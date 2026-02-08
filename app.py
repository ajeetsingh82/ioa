import os
import threading
import uvicorn
import logging
from uagents import Bureau
from pathlib import Path

# --- BASE DIRECTORY ---
# Define the root of the project.
BASE_DIR = Path(__file__).resolve().parent
os.environ['IOA_BASE_DIR'] = str(BASE_DIR)

# --- Imports ---
from src.init_agents import init_agents
from src.agents.gateway import gateway

# HTTP gateway imports
from gateway_http import create_app

# ============================================================
# HTTP Server
# ============================================================

gateway_http_host = "127.0.0.1"
gateway_http_port = 9000


def run_gateway_http():
    app = create_app(gateway.query_queue)
    uvicorn.run(
        app,
        host=gateway_http_host,
        port=gateway_http_port,
        log_level="info",
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    # Configure root logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("Main")

    # Suppress 'primp' logger INFO messages
    logging.getLogger("primp").setLevel(logging.WARNING)

    # Set environment variables for UserProxy / UI
    os.environ["GATEWAY_ADDRESS"] = f"http://{gateway_http_host}:{gateway_http_port}/submit"
    os.environ["CHAT_SERVER_URL"] = "http://localhost:8080/api/result"

    # Initialize agents
    conductor, strategist, scout, filter_agent, architect, program_of_thought = init_agents()

    # Create Bureau
    bureau = Bureau(port=8000)
    bureau.add(conductor)
    bureau.add(gateway)
    bureau.add(strategist)
    bureau.add(architect)
    bureau.add(program_of_thought)
    bureau.add(scout)
    bureau.add(filter_agent)

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_gateway_http, daemon=True)
    http_thread.start()

    logger.info(f"Gateway HTTP running on http://{gateway_http_host}:{gateway_http_port}")
    logger.info("Starting Agent Bureau on port 8000...")

    # Start Bureau (blocking call)
    bureau.run()

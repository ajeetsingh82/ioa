# This is the entry point for the web application (the user interface).
# It runs as a separate process from the agent bureau.

from src.servers.chat import run_chat_server

if __name__ == "__main__":
    # The gateway address is hardcoded for simplicity, as the agent bureau
    # will be running on a known port (8000).
    GATEWAY_AGENT_ADDRESS = "http://127.0.0.1:8000"
    run_chat_server(GATEWAY_AGENT_ADDRESS)

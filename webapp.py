# This is the entry point for the web application (the user interface).
# It runs as a separate process from the agent bureau.
import os
from src.servers.chat import run_chat_server

if __name__ == "__main__":
    # Define the address where this web app will run
    HOST = "127.0.0.1"
    PORT = 8080
    
    # Set the environment variable for the UserProxy agent to find this server
    chat_server_url = f"http://{HOST}:{PORT}/api/result"
    os.environ["CHAT_SERVER_URL"] = chat_server_url
    
    print(f"[WebApp] CHAT_SERVER_URL set to: {chat_server_url}")

    # Start the chat server
    # The server will read the GATEWAY_ADDRESS from its own environment.
    run_chat_server(host=HOST, port=PORT)

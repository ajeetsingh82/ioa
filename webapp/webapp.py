# This is the entry point for the web application (the user interface).
# It runs as a separate process from the agent bureau.
import os
from servers.chat import run_chat_server

if __name__ == "__main__":
    # Define the address where this web app will run
    HOST = "0.0.0.0" # Use 0.0.0.0 to be accessible from outside the container
    PORT = 8080
    
    # This env var is now more for local runs; in Docker, this will be handled by container networking.
    chat_server_url = f"http://localhost:{PORT}/api/result"
    os.environ["CHAT_SERVER_URL"] = chat_server_url
    
    print(f"[WebApp] CHAT_SERVER_URL set to: {chat_server_url}")

    # Start the chat server
    run_chat_server(host=HOST, port=PORT)

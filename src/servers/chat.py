import uvicorn
import asyncio
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
from uagents import Agent, Bureau # Bureau is not needed here anymore
from ..model.models import UserQuery

# -----------------------------
# Data Models
# -----------------------------

class ResultRequest(BaseModel):
    text: str
    request_id: str

# -----------------------------
# FastAPI App
# -----------------------------

app = FastAPI()

# Store active WebSocket connections and map request_id to WebSocket
active_connections: dict[str, WebSocket] = {}
request_to_connection_map: dict[str, str] = {} # Maps request_id to connection_id

# This will be set by the main app.py
gateway_agent_address: str | None = None # Now stores just the address string

# -----------------------------
# HTML/JavaScript for Chat UI
# -----------------------------

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """Serves the main chat interface HTML with WebSocket logic."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Agentic RAG Chat</title>
        <style>
            body { font-family: sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }
            #chat-container { max-width: 800px; margin: 20px auto; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); display: flex; flex-direction: column; height: calc(100vh - 40px); }
            h1 { text-align: center; color: #333; padding: 15px 0; border-bottom: 1px solid #eee; margin: 0; }
            #messages { flex-grow: 1; overflow-y: auto; padding: 15px; border-bottom: 1px solid #eee; }
            .message { margin-bottom: 10px; padding: 8px 12px; border-radius: 5px; max-width: 70%; }
            .user-message { background-color: #e0f7fa; align-self: flex-end; margin-left: auto; }
            .ai-message { background-color: #f0f0f0; align-self: flex-start; }
            .system-message { color: #888; font-style: italic; text-align: center; margin: 10px 0; }
            #input-area { display: flex; padding: 15px; border-top: 1px solid #eee; }
            #input-field { flex-grow: 1; padding: 10px; border: 1px solid #ccc; border-radius: 5px; margin-right: 10px; font-size: 16px; }
            #send-button { padding: 10px 15px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            #send-button:hover { background-color: #0056b3; }
        </style>
    </head>
    <body>
        <div id="chat-container">
            <h1>Agentic RAG System</h1>
            <div id="messages"></div>
            <div id="input-area">
                <input type="text" id="input-field" placeholder="Ask a question..." autocomplete="off">
                <button id="send-button">Send</button>
            </div>
        </div>

        <script>
            const messagesDiv = document.getElementById('messages');
            const inputField = document.getElementById('input-field');
            const sendButton = document.getElementById('send-button');
            let ws; // WebSocket connection

            function addMessage(sender, text, type = 'ai-message') {
                const messageElement = document.createElement('div');
                messageElement.classList.add('message', type);
                messageElement.innerHTML = `<strong>${sender}:</strong> ${text}`;
                messagesDiv.appendChild(messageElement);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }

            function generateRequestId() {
                return Date.now().toString(36) + Math.random().toString(36).substr(2);
            }

            function connectWebSocket() {
                ws = new WebSocket("ws://localhost:8080/ws");

                ws.onopen = (event) => {
                    console.log("WebSocket opened:", event);
                    addMessage('System', 'Connected to AI Assistant.', 'system-message');
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log("WebSocket message received:", data);
                    if (data.type === 'response') {
                        const thinkingMessage = document.querySelector(`.system-message[data-request-id="${data.request_id}"]`);
                        if (thinkingMessage) thinkingMessage.remove();
                        addMessage('AI Assistant', data.text);
                    } else if (data.type === 'status') {
                        const thinkingMessage = document.createElement('div');
                        thinkingMessage.classList.add('system-message');
                        thinkingMessage.setAttribute('data-request-id', data.request_id);
                        thinkingMessage.textContent = data.message;
                        messagesDiv.appendChild(thinkingMessage);
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    } else if (data.type === 'error') {
                        addMessage('System', `Error: ${data.message}`, 'system-message');
                    }
                };

                ws.onclose = (event) => {
                    console.log("WebSocket closed:", event);
                    addMessage('System', 'Disconnected. Reconnecting...', 'system-message');
                    setTimeout(connectWebSocket, 1000);
                };

                ws.onerror = (event) => {
                    console.error("WebSocket error:", event);
                    addMessage('System', 'WebSocket error occurred.', 'system-message');
                };
            }

            sendButton.addEventListener('click', sendMessage);
            inputField.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') sendMessage();
            });

            async function sendMessage() {
                const query = inputField.value.trim();
                if (!query) return;

                addMessage('You', query, 'user-message');
                inputField.value = '';

                if (ws.readyState === WebSocket.OPEN) {
                    const requestId = generateRequestId();
                    ws.send(JSON.stringify({ text: query, request_id: requestId }));
                } else {
                    addMessage('System', 'WebSocket not connected. Please wait.', 'system-message');
                }
            }

            connectWebSocket();
        </script>
    </body>
    </html>
    """

# -----------------------------
# WebSocket Endpoint
# -----------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global request_to_connection_map
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    active_connections[connection_id] = websocket
    
    try:
        while True:
            data = await websocket.receive_json()
            query_text = data.get("text")
            request_id = data.get("request_id")

            if not query_text or not request_id:
                await websocket.send_json({"type": "error", "message": "Invalid query or missing request_id."})
                continue

            request_to_connection_map[request_id] = connection_id

            # Send a message directly to the Gateway agent
            if gateway_agent_address: # Use the global address string
                # FastAPI cannot directly send uagents messages.
                # It must make an HTTP POST request to the uagents bureau's HTTP endpoint.
                # This is the correct way to bridge FastAPI to uagents.
                bureau_gateway_url = f"http://127.0.0.1:8000/submit" # The bureau's HTTP endpoint
                try:
                    await http_client.post(bureau_gateway_url, json={
                        "text": query_text,
                        "request_id": request_id
                    })
                except httpx.RequestError as e:
                    print(f"Error sending to bureau gateway: {e}")
                    await websocket.send_json({"type": "error", "message": f"Failed to send query to agent system: {e}"})
            else:
                await websocket.send_json({"type": "error", "message": "Agent system not connected."})

    except WebSocketDisconnect:
        del active_connections[connection_id]
        request_to_connection_map = {k:v for k,v in request_to_connection_map.items() if v != connection_id}
    except Exception as e:
        print(f"WebSocket error: {e}")

# -----------------------------
# Result Callback Endpoint
# -----------------------------

@app.post("/api/result")
async def handle_result(result: ResultRequest):
    """Receives the final result from the UserProxy Agent and pushes it to the correct client."""
    global request_to_connection_map
    connection_id = request_to_connection_map.pop(result.request_id, None)

    if connection_id and connection_id in active_connections:
        ws = active_connections[connection_id]
        try:
            await ws.send_json({
                "type": "response",
                "text": result.text,
                "request_id": result.request_id
            })
        except RuntimeError as e:
            print(f"Error sending to WebSocket {connection_id}: {e}")
    else:
        print(f"No active connection found for request_id: {result.request_id}")

    return {"status": "delivered"}

# -----------------------------
# Server Runner
# -----------------------------

def run_chat_server(gateway_addr: str): # Now accepts just the address string
    """Runs the FastAPI server."""
    global gateway_agent_address
    gateway_agent_address = gateway_addr # Set the global address
    
    print("[Chat Server] Starting FastAPI server on http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)

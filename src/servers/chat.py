import uvicorn
import os
import asyncio
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx

# --- Data Models ---
class ResultRequest(BaseModel):
    text: str
    request_id: str

# --- FastAPI App ---
app = FastAPI()
active_connections: dict[str, WebSocket] = {}
request_to_connection_map: dict[str, str] = {}

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """Serves the main chat interface HTML with WebSocket logic."""
    # The WebSocket URL is now dynamic based on the request
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
            let ws;

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
                const ws_protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
                const ws_url = `${ws_protocol}//${window.location.host}/ws`;
                ws = new WebSocket(ws_url);
                ws.onopen = () => addMessage('System', 'Connected to AI Assistant.', 'system-message');
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    const thinkingMessage = document.querySelector(`.system-message[data-request-id="${data.request_id}"]`);
                    if (thinkingMessage) thinkingMessage.remove();
                    addMessage('AI Assistant', data.text);
                };
                ws.onclose = () => {
                    addMessage('System', 'Disconnected. Reconnecting...', 'system-message');
                    setTimeout(connectWebSocket, 1000);
                };
                ws.onerror = () => addMessage('System', 'WebSocket error occurred.', 'system-message');
            }

            sendButton.addEventListener('click', sendMessage);
            inputField.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') sendMessage();
            });

            async function sendMessage() {
                const query = inputField.value.trim();
                if (!query) return;
                addMessage('You', query, 'user-message');
                const requestId = generateRequestId();
                const thinkingMessage = document.createElement('div');
                thinkingMessage.classList.add('system-message');
                thinkingMessage.setAttribute('data-request-id', requestId);
                thinkingMessage.textContent = 'Thinking...';
                messagesDiv.appendChild(thinkingMessage);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                inputField.value = '';
                if (ws.readyState === WebSocket.OPEN) {
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global request_to_connection_map
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    active_connections[connection_id] = websocket
    try:
        while True:
            data = await websocket.receive_json()
            request_id = data.get("request_id")
            request_to_connection_map[request_id] = connection_id
            
            # Read the gateway address from environment every time
            bureau_gateway_address = os.getenv("GATEWAY_ADDRESS", "http://127.0.0.1:8000/submit")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        bureau_gateway_address,
                        json={"text": data.get("text"), "request_id": request_id},
                        timeout=10.0
                    )
                    response.raise_for_status()
            except httpx.RequestError as e:
                print(f"[Chat Server] Error forwarding query to gateway: {e}")
                await websocket.send_json({"type": "error", "message": "Could not connect to agent system."})
    except WebSocketDisconnect:
        del active_connections[connection_id]
        request_to_connection_map = {k:v for k,v in request_to_connection_map.items() if v != connection_id}
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.post("/api/result")
async def handle_result(result: ResultRequest):
    global request_to_connection_map
    connection_id = request_to_connection_map.pop(result.request_id, None)
    if connection_id and connection_id in active_connections:
        ws = active_connections[connection_id]
        try:
            await ws.send_json({"type": "response", "text": result.text, "request_id": result.request_id})
        except RuntimeError as e:
            print(f"Error sending to WebSocket {connection_id}: {e}")
    return {"status": "delivered"}

def run_chat_server(host: str, port: int):
    """Runs the FastAPI server."""
    print(f"[Chat Server] Starting FastAPI server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

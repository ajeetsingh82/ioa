import uvicorn
import os
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# -------------------------------
# Logging
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-server")

# -------------------------------
# Data Models
# -------------------------------
class QueryRequest(BaseModel):
    text: str

class ResultRequest(BaseModel):
    text: str
    request_id: str
    type: int # -1: complete, 0: heartbeat, >0: more to follow

class RequestStatus(BaseModel):
    status: str
    text: Optional[str] = None
    error: Optional[str] = None

# -------------------------------
# Shared state
# -------------------------------
# request_id -> {"text": str, "status": "pending/done/failed", "result": str|None, "submitted_at": datetime}
pending_requests: Dict[str, Dict] = {}
state_lock = asyncio.Lock()
http_client: Optional[httpx.AsyncClient] = None

# -------------------------------
# Lifecycle Events
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    )
    logger.info("HTTP client initialized.")
    yield
    if http_client:
        await http_client.aclose()
        logger.info("HTTP client closed.")

# -------------------------------
# FastAPI App
# -------------------------------
app = FastAPI(title="AI Chat Server", lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Serve UI
# -------------------------------
@app.get("/", response_class=FileResponse)
async def get_chat_ui():
    """Serve ui.html from the local resources folder."""
    # This file is at webapp/servers/chat.py. We want webapp/resources/ui.html.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level from 'servers' to 'webapp', then into 'resources'
    file_path = os.path.join(os.path.dirname(current_dir), "resources", "ui.html")
    
    if not os.path.exists(file_path):
        # Fallback for running from root if needed, but the primary path should be correct
        file_path = os.path.join("webapp", "resources", "ui.html")
        if not os.path.exists(file_path):
            raise HTTPException(404, "UI file not found")
            
    return FileResponse(file_path, media_type="text/html")

# -------------------------------
# Submit query
# -------------------------------
@app.post("/api/query")
async def submit_query(query: QueryRequest):
    request_id = str(uuid.uuid4())
    async with state_lock:
        pending_requests[request_id] = {
            "text": query.text,
            "status": "pending",
            "result": "", # Initialize with empty string for streaming
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

    asyncio.create_task(forward_to_bureau(request_id, query.text))
    return {"request_id": request_id, "status": "pending"}

async def forward_to_bureau(request_id: str, text: str):
    # In Docker, this will be http://bureau:9000/submit
    bureau_url = os.getenv("GATEWAY_ADDRESS", "http://127.0.0.1:9000/submit")
    try:
        response = await http_client.post(bureau_url, json={"text": text, "request_id": request_id})
        response.raise_for_status()
        logger.info(f"Query forwarded to bureau ({bureau_url}): {request_id}")
    except httpx.RequestError as e:
        logger.error(f"Failed to forward query {request_id} to bureau ({bureau_url}): {e}")
        async with state_lock:
            if request_id in pending_requests:
                pending_requests[request_id]["status"] = "failed"
                pending_requests[request_id]["result"] = None

# -------------------------------
# Polling status
# -------------------------------
@app.get("/api/get_status/{request_id}", response_model=RequestStatus)
async def get_status(request_id: str):
    async with state_lock:
        req = pending_requests.get(request_id)
        if not req:
            return RequestStatus(status="failed", text=None, error="Unknown request_id")
        return RequestStatus(status=req["status"], text=req["result"])

# -------------------------------
# Streaming result (SSE)
# -------------------------------
@app.get("/api/stream_result/{request_id}")
async def stream_result(request_id: str):
    async def event_generator():
        last_pos = 0
        while True:
            async with state_lock:
                req = pending_requests.get(request_id)
                if not req:
                    yield f"data: {{'status':'failed','text':None,'error':'Unknown request_id'}}\n\n"
                    return
                
                full_text = req["result"] or ""
                status = req["status"]
                
                # Send only new content if any
                if len(full_text) > last_pos:
                    new_content = full_text[last_pos:]
                    # Escape newlines for SSE data field if needed, but usually client handles it.
                    # For simplicity, we send the whole text or diff. 
                    # Let's send the diff.
                    # Note: SSE format is "data: <payload>\n\n"
                    # If payload has newlines, we need to handle it.
                    # Simple approach: send JSON
                    import json
                    payload = json.dumps({"text": new_content, "status": status})
                    yield f"data: {payload}\n\n"
                    last_pos = len(full_text)
                elif status == "done":
                     # Send final done signal
                     import json
                     payload = json.dumps({"text": "", "status": "done"})
                     yield f"data: {payload}\n\n"
                     return
                elif status == "failed":
                     import json
                     payload = json.dumps({"text": "", "status": "failed"})
                     yield f"data: {payload}\n\n"
                     return

            if status == "done" or status == "failed":
                return

            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# -------------------------------
# Handle result callback from UserProxy / Bureau
# -------------------------------
@app.post("/api/result")
async def handle_result(result: ResultRequest):
    async with state_lock:
        req = pending_requests.get(result.request_id)
        if not req:
            logger.warning(f"Received result for unknown request_id {result.request_id}")
            return {"status": "unknown_request"}
        
        # Preserve Markdown formatting
        text = result.text.replace("\r\n", "\n")
        
        # Append text
        if req["result"] is None:
            req["result"] = ""
        req["result"] += text
        
        # Update status based on type
        if result.type == -1:
            req["status"] = "done"
        elif result.type >= 0:
            req["status"] = "pending" # Still pending/streaming
            
    logger.info(f"Result update for request_id {result.request_id}. Type: {result.type}")
    return {"status": "delivered", "text": text}

# -------------------------------
# Run server
# -------------------------------
def run_chat_server(host: str = "127.0.0.1", port: int = 8080):
    logger.info(f"Starting chat server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

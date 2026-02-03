import uvicorn
import os
import asyncio
import uuid
import logging
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-server")

# -------------------------------------------------
# Data Models
# -------------------------------------------------
class QueryRequest(BaseModel):
    text: str

class ResultRequest(BaseModel):
    text: str
    request_id: str

class RequestStatus(BaseModel):
    status: str
    text: str | None = None

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI()

# Allow cross-origin requests for UI served from another domain if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# -------------------------------------------------
# Shared state
# -------------------------------------------------
# request_id -> {"text": str, "status": "pending/done/failed", "result": str|None}
pending_requests: Dict[str, Dict] = {}
state_lock = asyncio.Lock()
http_client: httpx.AsyncClient | None = None

# -------------------------------------------------
# Lifecycle Events
# -------------------------------------------------
@app.on_event("startup")
async def startup_event():
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    )
    logger.info("HTTP client initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    global http_client
    if http_client:
        await http_client.aclose()
        logger.info("HTTP client closed.")

# -------------------------------------------------
# Serve UI
# -------------------------------------------------
@app.get("/", response_class=FileResponse)
async def get_chat_ui():
    """Serve ui.html from resources folder."""
    file_path = os.path.join(".", "resources", "ui.html")
    if not os.path.exists(file_path):
        raise HTTPException(404, "UI file not found")
    return FileResponse(file_path, media_type="text/html")

# -------------------------------------------------
# Polling: Receive new query
# -------------------------------------------------
@app.post("/api/query")
async def submit_query(query: QueryRequest):
    request_id = str(uuid.uuid4())
    async with state_lock:
        pending_requests[request_id] = {"text": query.text, "status": "pending", "result": None}

    # Send the query to the agent bureau asynchronously
    asyncio.create_task(forward_to_bureau(request_id, query.text))
    return {"request_id": request_id, "status": "pending"}

async def forward_to_bureau(request_id: str, text: str):
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

# -------------------------------------------------
# Polling: Check status
# -------------------------------------------------
@app.get("/api/get_status/{request_id}", response_model=RequestStatus)
async def get_status(request_id: str):
    async with state_lock:
        req = pending_requests.get(request_id)
        if not req:
            return RequestStatus(status="failed", text=None)
        return RequestStatus(status=req["status"], text=req["result"])

# -------------------------------------------------
# Result Callback from UserProxy / Bureau
# -------------------------------------------------
@app.post("/api/result")
async def handle_result(result: ResultRequest):
    async with state_lock:
        if result.request_id not in pending_requests:
            logger.warning(f"Received result for unknown request_id {result.request_id}")
            return {"status": "unknown_request"}
        pending_requests[result.request_id]["status"] = "done"
        pending_requests[result.request_id]["result"] = result.text
    logger.info(f"Result stored for request_id {result.request_id}")
    return {"status": "delivered"}

# -------------------------------------------------
# Run server
# -------------------------------------------------
def run_chat_server(host: str = "127.0.0.1", port: int = 8080):
    logger.info(f"Starting server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

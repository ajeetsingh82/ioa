from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from model.models import UserQuery
from queue import Queue

def create_app(queue: Queue):
    app = FastAPI()

    class SubmitRequest(BaseModel):
        text: str
        request_id: str

    @app.post("/submit")
    async def submit(req: SubmitRequest):
        # Log the incoming request_id
        print(f"Received request - ID: {req.request_id}")

        # Put message into gateway queue
        queue.put(
            UserQuery(
                text=req.text,
                request_id=req.request_id,
            )
        )

        return {"status": "accepted"}
    
    return app

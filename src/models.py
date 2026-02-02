from uagents import Model
from typing import List, Optional
import uuid

# The initial query from the user to the orchestrator
class UserQuery(Model):
    text: str
    request_id: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())

# The message from the orchestrator to the workers
class MissionBrief(Model):
    request_id: str
    sub_task: str
    labels: List[str]
    orchestrator_address: str

# The message from a worker to the orchestrator upon completion
class WorkerCompletion(Model):
    request_id: str
    worker_name: str
    status: str # e.g., "Completed", "Failed"

# The message from the orchestrator to the synthesis agent
class SynthesisRequest(Model):
    request_id: str
    original_query: str
    labels: List[str]
    user_agent_address: str # To send the final response back

# The final response message from the synthesis agent to the user agent
class Query(Model):
    text: str
    request_id: Optional[str] = None

# Worker/Agent registration message
class AgentRegistration(Model):
    agent_name: str
    agent_type: str # "worker" or "synthesis"

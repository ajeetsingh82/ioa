from uagents import Model
from typing import List, Optional
import uuid

# --- Core Agentic Models ---

class AgentRegistration(Model):
    """Message to register an agent with the registry."""
    agent_type: str

class TaskCompletion(Model):
    """Generic message to signal the completion of a task."""
    request_id: str
    label: str

class NewPipeline(Model):
    """Signal from the Strategist to the Conductor that a new pipeline is ready."""
    request_id: str

# --- User Interaction Models ---

class UserQuery(Model):
    """The initial query from the user to the system."""
    text: str
    request_id: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())

class DisplayResponse(Model):
    """The final, formatted response sent to the user's screen."""
    text: str

# --- Scout Agent Models ---

class ScoutRequest(Model):
    """Message from the Conductor to a Scout agent."""
    request_id: str
    sub_query: str
    label: str

class ScoutResponse(Model):
    """Message from a Scout agent back to the Conductor."""
    request_id: str
    content: str
    label: str

# --- Filter Agent Models ---

class FilterRequest(Model):
    """Message from the Conductor to a Filter agent."""
    request_id: str
    content: str
    label: str
    original_query: str

# --- Architect Agent Models ---

class ArchitectRequest(Model):
    """Message from the Conductor to the Architect agent."""
    request_id: str
    original_query: str
    labels: List[str]

class ArchitectResponse(Model):
    """Structured response from the Architect to the User Proxy."""
    request_id: str
    status: str  # "success" or "failure"
    synthesized_data: str

# --- Program of Thought Models ---

class CodeExecutionRequest(Model):
    """Request to execute Python code."""
    request_id: str
    code: str
    timeout: int = 5

class CodeExecutionResponse(Model):
    """Response containing the execution result."""
    request_id: str
    stdout: str
    stderr: str
    exit_code: int
    status: str # "success", "error", "timeout"

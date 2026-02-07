from uagents import Model
from typing import List, Optional, Dict, Any
import uuid

# --- Core Agentic Models ---

class AgentRegistration(Model):
    """Message to register an agent with the registry."""
    agent_type: str

class NewPipeline(Model):
    """Signal from the Strategist to the Conductor that a new pipeline is ready."""
    request_id: str

# --- Generic Cognitive Model ---

class CognitiveMessage(Model):
    """
    A unified message model for all agent-to-agent communication.
    
    Attributes:
        request_id: The correlation ID for the user query.
        type: The intent or action type (e.g., "SEARCH", "FILTER", "SYNTHESIZE", "CODE_EXEC").
        content: The main payload (query, text, code, etc.).
        metadata: Additional context (labels, original query, etc.).
    """
    request_id: str
    type: str 
    content: str
    metadata: Dict[str, str] = {}

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

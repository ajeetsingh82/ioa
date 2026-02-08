from uagents import Model
from typing import List, Optional, Dict, Any
import uuid
from enum import Enum

# --- Type Definitions for Agent Communication ---

class AgentGoalType(Enum):
    """Defines the valid types for goals assigned to agents."""
    PLAN = "plan"
    SYNTHESYS = "synthesys"
    TASK = "task"
    UNKNOWN = "unknown"

class ThoughtType(Enum):
    """Defines the valid types for thoughts (outcomes) from agents."""
    SUB_GOAL = "sub goal"
    USER_QUERY = "sub user query"
    RESOLVED = "Resolved"
    FAILED = "Failed"
    ANSWER = "answer"  # Special case for the final answer from the Architect

# --- Core Agentic Models ---

class AgentRegistration(Model):
    """Message to register an agent with the registry."""
    agent_type: str

class ReplanRequest(Model):
    """Message from the Orchestrator to the Conductor when a graph stalls."""
    request_id: str
    reason: str

# --- Generic Cognitive Model ---

class AgentGoal(Model):
    """
    A unified message model for assigning tasks (goals) to agents.
    
    Attributes:
        request_id: The correlation ID for the user query.
        type: The goal type, should be a value from AgentGoalType.
        content: The main payload for the goal (query, text, code, etc.).
        metadata: Additional context (labels, original query, etc.).
    """
    request_id: str
    type: AgentGoalType
    content: str
    metadata: Dict[str, str] = {}

class Thought(Model):
    """

    A unified message model for agent responses, representing the outcome of a goal.
    
    Attributes:
        request_id: The correlation ID for the user query.
        type: The outcome status, should be a value from ThoughtType.
        content: The result or error message.
        impressions: A list of keys from the shared memory that are relevant to this thought.
        metadata: Additional context, including the original goal type.
    """
    request_id: str
    type: ThoughtType
    content: str
    impressions: List[str] = []
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

class Response(Model):
    """The response from the system to the Gateway."""
    request_id: str
    content: str
    type: int # -1: complete, 0: heartbeat, >0: more to follow

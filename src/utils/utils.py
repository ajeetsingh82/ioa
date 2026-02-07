from ..agents.scout import AGENT_TYPE_RETRIEVE
from ..agents.filter import AGENT_TYPE_FILTER
from ..agents.architect import AGENT_TYPE_SYNTHESIZE
from ..agents.program_of_thought import AGENT_TYPE_COMPUTE

def to_msg_type(agent_type: str) -> str:
    """
    Converts an agent type to its corresponding message type for instructions.
    """
    if agent_type == AGENT_TYPE_RETRIEVE:
        return "SEARCH"
    elif agent_type == AGENT_TYPE_FILTER:
        return "FILTER"
    elif agent_type == AGENT_TYPE_SYNTHESIZE:
        return "SYNTHESIZE"
    elif agent_type == AGENT_TYPE_COMPUTE:
        return "CODE_EXEC"
    else:
        return "UNKNOWN"

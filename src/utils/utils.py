from enum import Enum
from typing import Type, TypeVar, Optional

from ..agents.scout import AGENT_TYPE_RETRIEVE
from ..agents.filter import AGENT_TYPE_FILTER
from ..agents.architect import AGENT_TYPE_SYNTHESIZE
from ..agents.pot import AGENT_TYPE_COMPUTE
from ..model.models import AgentGoalType

E = TypeVar("E", bound=Enum)

def str_to_enum(
    enum_cls: Type[E],
    value: str,
    *,
    case_sensitive: bool = False,
    default: Optional[E] = None
) -> E:
    """
    Converts a string to an enum member, with optional case-insensitivity and a default value.
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected string for enum conversion, got {type(value)}")

    try:
        if case_sensitive:
            return enum_cls(value)

        # case-insensitive match
        for member in enum_cls:
            if member.value.lower() == value.lower():
                return member

        raise ValueError

    except ValueError:
        if default is not None:
            return default
        raise ValueError(
            f"'{value}' is not a valid {enum_cls.__name__}. "
            f"Allowed values: {[m.value for m in enum_cls]}"
        )

def get_goal_type(agent_type: str) -> AgentGoalType:
    """
    Maps an agent's type string to the corresponding AgentGoalType enum member.
    """
    if agent_type == AGENT_TYPE_RETRIEVE:
        return AgentGoalType.SEARCH
    elif agent_type == AGENT_TYPE_FILTER:
        return AgentGoalType.FILTER
    elif agent_type == AGENT_TYPE_SYNTHESIZE:
        return AgentGoalType.SYNTHESIZE
    elif agent_type == AGENT_TYPE_COMPUTE:
        return AgentGoalType.CODE_EXEC
    else:
        raise ValueError(f"No AgentGoalType defined for agent type '{agent_type}'")

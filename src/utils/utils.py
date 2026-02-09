import re
from enum import Enum
from typing import Type, TypeVar, Optional
from ..model.agent_types import AgentType
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
    if agent_type == AgentType.SYNTHESIZE.value:
        return AgentGoalType.SYNTHESYS
    else:
        return AgentGoalType.TASK

def clean_gateway_response(text: str) -> str:
    text = re.sub(r"<\|start_header_id\|>.*?<\|end_header_id\|>", "", text, flags=re.S)
    text = re.sub(r"<\|.*?\|>", "", text)
    return text.strip()
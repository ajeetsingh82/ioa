from uagents import Agent

from .ioa import ConductorAgent
from .agents.gateway import gateway
from .agents.planner import PlannerAgent
from .agents.scout import ScoutAgent
from .agents.filter import FilterAgent
from .agents.architect import ArchitectAgent
from .agents.pot import ProgramOfThoughtAgent

# ============================================================
# Agent Initialization
# ============================================================

def init_agents():
    """
    Initializes all agents in the system and configures their relationships.
    Returns a tuple of (conductor, planner, scout, filter_agent, architect, program_of_thought).
    """
    conductor = ConductorAgent(name="conductor", seed="conductor_seed")

    planner = PlannerAgent(
        name="planner",
        seed="planner_seed",
    )

    scout = ScoutAgent(
        name="scout",
        seed="scout_seed",
    )

    filter_agent = FilterAgent(
        name="filter",
        seed="filter_seed",
    )

    architect = ArchitectAgent(
        name="architect",
        seed="architect_seed",
    )

    program_of_thought = ProgramOfThoughtAgent(
        name="program_of_thought",
        seed="program_of_thought_seed",
    )

    # Gateway is self-configuring via the registry and global import

    return conductor, planner, scout, filter_agent, architect, program_of_thought

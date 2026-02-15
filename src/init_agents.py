from uagents import Agent

from .ioa import ConductorAgent
from .agents.gateway import gateway
from .agents.planner import PlannerAgent
from .agents.architect import ArchitectAgent
from .agents.pot import ProgramOfThoughtAgent
from .agents.retrieve import RetrieveAgent

# ============================================================
# Agent Initialization
# ============================================================

def init_agents() -> list[Agent]:
    """
    Initializes all agents in the system.
    Returns a list containing all initialized agents.
    """
    conductor = ConductorAgent(name="conductor", seed="conductor_seed")

    planner = PlannerAgent(
        name="planner",
        seed="planner_seed",
    )

    architect = ArchitectAgent(
        name="architect",
        seed="architect_seed",
    )

    program_of_thought = ProgramOfThoughtAgent(
        name="program_of_thought",
        seed="program_of_thought_seed",
    )

    retrieve = RetrieveAgent(
        name="retrieve",
        seed="retrieve_seed",
    )

    # The gateway is also included for completeness, though it's a global instance.
    return [conductor, gateway, planner, architect, program_of_thought, retrieve]

from uagents import Agent

from .ioa import ConductorAgent
from .agents.gateway import gateway
from .agents.strategist import StrategistAgent
from .agents.scout import ScoutAgent
from .agents.filter import FilterAgent
from .agents.architect import ArchitectAgent
from .agents.pot import ProgramOfThoughtAgent

# ============================================================
# Agent Initialization
# ============================================================
DEPTH = 10

def init_agents():
    """
    Initializes all agents in the system and configures their relationships.
    Returns a tuple of (conductor, strategist, scouts, filters, architect, program_of_thought).
    """
    conductor = ConductorAgent(name="conductor", seed="conductor_seed")

    strategist = StrategistAgent(
        name="strategist",
        seed="strategist_seed",
        conductor_address=conductor.address,
    )

    scouts = [
        ScoutAgent(
            name=f"scout_{i}",
            seed=f"scout_seed_{i}",
            conductor_address=conductor.address,
        )
        for i in range(DEPTH)
    ]

    filters = [
        FilterAgent(
            name=f"filter_{i}",
            seed=f"filter_seed_{i}",
            conductor_address=conductor.address,
        )
        for i in range(DEPTH)
    ]

    architect = ArchitectAgent(
        name="architect",
        seed="architect_seed",
        conductor_address=conductor.address,
    )

    program_of_thought = ProgramOfThoughtAgent(
        name="program_of_thought",
        seed="program_of_thought_seed",
        conductor_address=conductor.address,
    )

    # Configure gateway
    gateway.strategist_address = strategist.address
    gateway._conductor_address = conductor.address # Manually set conductor address for BaseAgent registration

    return conductor, strategist, scouts, filters, architect, program_of_thought

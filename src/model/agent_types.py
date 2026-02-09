from enum import Enum

class AgentType(str, Enum):
    PLANNER = "planner" #planning
    RETRIEVE = "retrieve" # vector db retrieve
    SCOUT = "scout" # web content filtering
    SEMANTICS = "semantics" # give me semantic numerical vector against query or text
    CODER = "coder" # code generation
    COMPUTE = "compute" # only executes no llm interaction
    REASON = "reason" # deep reasoning
    SYNTHESIZE = "synthesize" # answer user query against combined data context
    VALIDATE = "validate" # validate query answer
    SPEAKER = "speaker" # this handles user interaction so strict formating of response text
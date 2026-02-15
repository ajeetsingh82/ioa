import os
from .agent_types import AgentType

# Base URL (can be overridden via env)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaModelRegistry:
    """
    Centralized model configuration registry for all agent types.
    Standardized on Ollama /api/chat for all LLM-based agents.
    """

    def __init__(self):

        # -------- Default LLM Config --------
        self.DEFAULT_MODEL_CONFIG = {
            "model": "llama3.2:1b",
            "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
            "api_type": "chat",
            "temperature": 0.3,
            "max_tokens": 1024,
            "description": "Default fallback reasoning model"
        }

        # -------- Agent Model Mapping --------
        self.AGENT_MODEL_REGISTRY = {

            AgentType.PLANNER: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.2,
                "max_tokens": 2048,
                "description": "Execution graph planning and task decomposition"
            },

            AgentType.RETRIEVE: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.2,
                "max_tokens": 512,
                "description": "Vector DB query refinement and keyword extraction"
            },

            AgentType.SCOUT: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.3,
                "max_tokens": 1024,
                "description": "Web content filtering and relevance detection"
            },

            AgentType.SEMANTICS: {
                "model": "nomic-embed-text",
                "endpoint": f"{OLLAMA_BASE_URL}/api/embeddings",
                "api_type": "embeddings",
                "description": "Embedding vector generation"
            },

            AgentType.CODER: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.0,
                "max_tokens": 2048,
                "description": "Code generation"
            },

            AgentType.COMPUTE: {
                "model": None,
                "endpoint": None,
                "api_type": "internal",
                "description": "Pure execution agent (no LLM interaction)"
            },

            AgentType.REASON: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.3,
                "max_tokens": 2048,
                "description": "Deep reasoning and multi-step logic"
            },

            AgentType.SYNTHESIZE: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.4,
                "max_tokens": 2048,
                "description": "Combining retrieved and reasoned data"
            },

            AgentType.VALIDATE: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.1,
                "max_tokens": 512,
                "description": "Confidence scoring and validation"
            },

            AgentType.SPEAKER: {
                "model": "llama3.2:1b",
                "endpoint": f"{OLLAMA_BASE_URL}/api/chat",
                "api_type": "chat",
                "temperature": 0.2,
                "max_tokens": 1024,
                "description": "User-facing formatted response generation"
            },
        }

    def get_agent_model_config(self, agent_type: AgentType | str) -> dict:
        """
        Returns model configuration for the given agent type.
        Falls back to default if not found.
        """

        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type.lower())
            except ValueError:
                return self.DEFAULT_MODEL_CONFIG

        return self.AGENT_MODEL_REGISTRY.get(agent_type, self.DEFAULT_MODEL_CONFIG)


# Global instance
model_registry = OllamaModelRegistry()

import os
import yaml
from pathlib import Path
from collections import defaultdict

class AgentConfig:
    """A simple data class to hold the configuration for a single agent."""
    def __init__(self, agent_type, prompts, schemas):
        self.type = agent_type
        self.prompts = prompts
        self.schemas = schemas

    def get_prompt(self, name="default"):
        return self.prompts.get(name)

    def get_schema(self, name):
        return self.schemas.get(name)

class AgentConfigStore:
    """
    A central store for agent configurations. It loads all agent YAML files
    from a specified directory and provides a simple interface to access them.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AgentConfigStore, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_dir=None):
        # This check prevents re-initialization on subsequent calls
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            base_dir = Path(os.getenv('IOA_BASE_DIR', Path(__file__).resolve().parent.parent.parent))
            self.config_dir = base_dir / "config" / "agents"
            
        self._configs = {}
        self._load_configs()
        self._initialized = True

    def _load_configs(self):
        """Loads all agent configurations from the .yaml files in the config directory."""
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Agent configuration directory not found at {self.config_dir}")

        for filename in os.listdir(self.config_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                file_path = self.config_dir / filename
                with open(file_path, "r") as f:
                    try:
                        data = yaml.safe_load(f)
                        agent_type = data.get("agent_type")

                        if not agent_type:
                            print(f"Warning: 'agent_type' not defined in {filename}")
                            continue
                        
                        prompts = {p['name']: p['text'].strip() for p in data.get('prompts', [])}
                        schemas = {s['name']: s['definition'] for s in data.get('schemas', [])}

                        self._configs[agent_type] = AgentConfig(agent_type, prompts, schemas)

                    except (yaml.YAMLError, KeyError, TypeError) as e:
                        print(f"Error processing YAML file {filename}: {e}")

    def get_config(self, agent_type: str) -> AgentConfig:
        """
        Retrieves the configuration for a specific agent type.
        
        Args:
            agent_type: The type of the agent (e.g., 'strategist').
            
        Returns:
            An AgentConfig object or None if not found.
        """
        return self._configs.get(agent_type)

# --- Global Singleton Instance ---
# Agents can import this instance directly to access their configs.
# Example:
# from src.config.store import agent_config_store
# strategist_config = agent_config_store.get_config('strategist')
# planner_prompt = strategist_config.get_prompt('planner')

agent_config_store = AgentConfigStore()

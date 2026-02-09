import subprocess
import tempfile
import os
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought, AgentGoal, AgentGoalType, ThoughtType
from ..config.store import agent_config_store
from ..model.agent_types import AgentType

class ProgramOfThoughtAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str = None):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AgentType.COMPUTE
        
        config = agent_config_store.get_config(self.type.value)
        if not config:
            raise ValueError(f"Configuration for agent type '{self.type.value}' not found.")
        self.prompt = config.get_prompt('default')
        if not self.prompt:
            raise ValueError(f"Prompt 'default' not found for agent type '{self.type.value}'.")
            
        self.on_message(model=AgentGoal)(self.process_code_execution)

    async def process_code_execution(self, ctx: Context, sender: str, msg: AgentGoal):
        """
        Executes the provided Python code and returns the output as a Thought.
        """
        if msg.type != AgentGoalType.TASK:
            ctx.logger.warning(f"ProgramOfThought received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Processing code execution request {msg.request_id}")
        
        code = msg.content
        timeout = int(msg.metadata.get("timeout", "5"))
        metadata = msg.metadata.copy()
        metadata["goal_type"] = str(msg.type)

        response_type = ThoughtType.FAILED
        response_content = ""

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file_path = f.name

            try:
                result = subprocess.run(
                    ["python3", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode == 0:
                    response_type = ThoughtType.RESOLVED
                    response_content = result.stdout
                else:
                    response_content = result.stderr

                metadata["exit_code"] = str(result.returncode)
                
            except subprocess.TimeoutExpired:
                ctx.logger.warning(f"Code execution timed out for request {msg.request_id}")
                response_content = "Execution timed out."
                metadata["exit_code"] = "-1"
            except Exception as e:
                ctx.logger.error(f"Error executing code for request {msg.request_id}: {e}")
                response_content = str(e)
                metadata["exit_code"] = "-1"
            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        except Exception as e:
             ctx.logger.error(f"Failed to create temporary file for request {msg.request_id}: {e}")
             response_content = f"System error: {str(e)}"
             metadata["exit_code"] = "-1"

        await ctx.send(sender, Thought(
            request_id=msg.request_id,
            type=response_type,
            content=response_content,
            metadata=metadata
        ))
        ctx.logger.info(f"Sent execution result for request {msg.request_id}. Status: {response_type}")

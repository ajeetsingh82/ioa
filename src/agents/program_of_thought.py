import subprocess
import tempfile
import os
from uagents import Context
from .base import BaseAgent
from ..model.models import Thought

AGENT_TYPE_COMPUTE = "COMPUTE"

class ProgramOfThoughtAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_COMPUTE
        self.on_message(model=Thought)(self.execute_code)

    async def execute_code(self, ctx: Context, sender: str, msg: Thought):
        """
        Executes the provided Python code in a subprocess and returns the output.
        """
        if msg.type != "CODE_EXEC":
            ctx.logger.warning(f"ProgramOfThought received unknown message type: {msg.type}")
            return

        ctx.logger.info(f"Received code execution request {msg.request_id}")
        
        code = msg.content
        timeout = int(msg.metadata.get("timeout", "5"))
        metadata = msg.metadata.copy()

        # Create a temporary file for the code
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file_path = f.name

            # Execute the code
            try:
                result = subprocess.run(
                    ["python3", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                status = "success" if result.returncode == 0 else "error"
                
                metadata["stderr"] = result.stderr
                metadata["exit_code"] = str(result.returncode)
                metadata["status"] = status

                response = Thought(
                    request_id=msg.request_id,
                    type="CODE_RESULT",
                    content=result.stdout,
                    metadata=metadata
                )
                
            except subprocess.TimeoutExpired:
                ctx.logger.warning(f"Code execution timed out for request {msg.request_id}")
                metadata["stderr"] = "Execution timed out."
                metadata["exit_code"] = "-1"
                metadata["status"] = "timeout"
                response = Thought(
                    request_id=msg.request_id,
                    type="CODE_RESULT",
                    content="",
                    metadata=metadata
                )
            except Exception as e:
                ctx.logger.error(f"Error executing code for request {msg.request_id}: {e}")
                metadata["stderr"] = str(e)
                metadata["exit_code"] = "-1"
                metadata["status"] = "error"
                response = Thought(
                    request_id=msg.request_id,
                    type="CODE_RESULT",
                    content="",
                    metadata=metadata
                )
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        except Exception as e:
             ctx.logger.error(f"Failed to create temporary file for request {msg.request_id}: {e}")
             metadata["stderr"] = f"System error: {str(e)}"
             metadata["exit_code"] = "-1"
             metadata["status"] = "error"
             response = Thought(
                request_id=msg.request_id,
                type="CODE_RESULT",
                content="",
                metadata=metadata
            )

        await ctx.send(sender, response)
        ctx.logger.info(f"Sent execution result for request {msg.request_id}. Status: {response.metadata.get('status')}")

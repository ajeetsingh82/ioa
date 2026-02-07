import subprocess
import tempfile
import os
from uagents import Context
from .base import BaseAgent
from ..model.models import CodeExecutionRequest, CodeExecutionResponse

AGENT_TYPE_COMPUTE = "COMPUTE"

class ProgramOfThoughtAgent(BaseAgent):
    def __init__(self, name: str, seed: str, conductor_address: str):
        super().__init__(name=name, seed=seed, conductor_address=conductor_address)
        self.type = AGENT_TYPE_COMPUTE
        self.on_message(model=CodeExecutionRequest)(self.execute_code)

    async def execute_code(self, ctx: Context, sender: str, msg: CodeExecutionRequest):
        """
        Executes the provided Python code in a subprocess and returns the output.
        """
        ctx.logger.info(f"Received code execution request {msg.request_id}")
        
        # Create a temporary file for the code
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(msg.code)
                temp_file_path = f.name

            # Execute the code
            try:
                result = subprocess.run(
                    ["python3", temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=msg.timeout
                )
                
                status = "success" if result.returncode == 0 else "error"
                
                response = CodeExecutionResponse(
                    request_id=msg.request_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    status=status
                )
                
            except subprocess.TimeoutExpired:
                ctx.logger.warning(f"Code execution timed out for request {msg.request_id}")
                response = CodeExecutionResponse(
                    request_id=msg.request_id,
                    stdout="",
                    stderr="Execution timed out.",
                    exit_code=-1,
                    status="timeout"
                )
            except Exception as e:
                ctx.logger.error(f"Error executing code for request {msg.request_id}: {e}")
                response = CodeExecutionResponse(
                    request_id=msg.request_id,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                    status="error"
                )
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        except Exception as e:
             ctx.logger.error(f"Failed to create temporary file for request {msg.request_id}: {e}")
             response = CodeExecutionResponse(
                request_id=msg.request_id,
                stdout="",
                stderr=f"System error: {str(e)}",
                exit_code=-1,
                status="error"
            )

        await ctx.send(sender, response)
        ctx.logger.info(f"Sent execution result for request {msg.request_id}. Status: {response.status}")

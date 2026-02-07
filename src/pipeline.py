# This module encapsulates all logic for managing cognitive task pipelines.
import asyncio
import uuid
from typing import List, Dict, Any, Optional

class PipelineStep:
    """
    Represents a single step in the execution pipeline.
    """
    def __init__(self, agent_type: str, content: str, metadata: Dict[str, str] = None, dependencies: List[str] = None):
        self.id = str(uuid.uuid4())
        self.agent_type = agent_type
        self.content = content # The input for the agent
        self.metadata = metadata or {}
        self.dependencies = dependencies or [] # List of step IDs that must complete before this step
        self.status = "PENDING" # PENDING, RUNNING, COMPLETED, FAILED
        self.result: Optional[str] = None

class Pipeline:
    """
    Manages the state and progression of a single user request's task pipeline.
    """
    def __init__(self, request_id: str, original_query: str):
        self.request_id = request_id
        self.original_query = original_query
        self.steps: List[PipelineStep] = []
        self.results: Dict[str, str] = {} # Map step_id -> result content
        self.completed_steps = 0

    def add_step(self, step: PipelineStep):
        self.steps.append(step)

    def get_executable_steps(self) -> List[PipelineStep]:
        """Returns a list of steps that are PENDING and have all dependencies met."""
        executable = []
        for step in self.steps:
            if step.status == "PENDING":
                deps_met = all(dep_id in self.results for dep_id in step.dependencies)
                if deps_met:
                    executable.append(step)
        return executable

    def get_step(self, step_id: str) -> Optional[PipelineStep]:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def mark_step_running(self, step_id: str):
        step = self.get_step(step_id)
        if step:
            step.status = "RUNNING"

    def mark_step_complete(self, step_id: str, result: str):
        step = self.get_step(step_id)
        if step:
            step.status = "COMPLETED"
            step.result = result
            self.results[step_id] = result
            self.completed_steps += 1

    def is_complete(self) -> bool:
        return all(step.status == "COMPLETED" for step in self.steps)

class PipelineManager:
    """
    Manages all active Pipeline instances.
    """
    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}
        self._lock = asyncio.Lock()

    async def create_pipeline(self, request_id: str, original_query: str) -> Pipeline:
        """Creates and stores a new Pipeline instance."""
        async with self._lock:
            pipeline = Pipeline(request_id, original_query)
            self._pipelines[request_id] = pipeline
            return pipeline

    async def get_pipeline(self, request_id: str) -> Pipeline | None:
        """Retrieves an active pipeline."""
        async with self._lock:
            return self._pipelines.get(request_id)

    async def remove_pipeline(self, request_id: str):
        """Deletes a completed pipeline."""
        async with self._lock:
            if request_id in self._pipelines:
                del self._pipelines[request_id]

# Instantiate a single manager to be used by the orchestrator
pipeline_manager = PipelineManager()

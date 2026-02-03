# This module encapsulates all logic for managing cognitive task pipelines.
from typing import List, Dict, Any

class Pipeline:
    """
    Manages the state and progression of a single user request's task pipeline.
    This now includes separate queues for different stages of the process.
    """
    def __init__(self, request_id: str, tasks: List[Dict[str, Any]], user_agent_address: str, original_query: str):
        self.request_id = request_id
        
        # The initial tasks from the Strategist are scout tasks
        self.scout_tasks: List[Dict[str, Any]] = tasks
        
        self.total_tasks = len(tasks)
        self.completed_tasks = 0
        self.user_agent_address = user_agent_address
        self.original_query = original_query
        self.all_labels = [task.get('label', 'general') for task in tasks]

    def has_pending_scout_tasks(self) -> bool:
        """Checks if there are tasks waiting for a Scout."""
        return len(self.scout_tasks) > 0

    def get_next_scout_task(self) -> Dict[str, Any] | None:
        """Pops the next scout task from the queue."""
        if not self.scout_tasks:
            return None
        return self.scout_tasks.pop(0)

    def complete_task(self):
        """Increments the completed task counter."""
        self.completed_tasks += 1

    def is_complete(self) -> bool:
        """Checks if all tasks in the pipeline are complete."""
        return self.completed_tasks >= self.total_tasks

class PipelineManager:
    """
    Manages all active Pipeline instances.
    """
    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}

    def create_pipeline(self, request_id: str, tasks: List[Dict[str, Any]], user_agent_address: str, original_query: str):
        """Creates and stores a new Pipeline instance."""
        if request_id not in self._pipelines:
            self._pipelines[request_id] = Pipeline(request_id, tasks, user_agent_address, original_query)

    def get_pipeline(self, request_id: str) -> Pipeline | None:
        """Retrieves an active pipeline."""
        return self._pipelines.get(request_id)

    def remove_pipeline(self, request_id: str):
        """Deletes a completed pipeline."""
        if request_id in self._pipelines:
            del self._pipelines[request_id]

    def get_active_pipelines(self) -> List[Pipeline]:
        """Returns a list of all pipelines that are not yet complete."""
        return [p for p in self._pipelines.values() if not p.is_complete()]

# Instantiate a single manager to be used by the orchestrator
pipeline_manager = PipelineManager()

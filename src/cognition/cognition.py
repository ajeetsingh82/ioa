# This module implements the Global Working Memory (Shared Blackboard).
# For simplicity, this will be an in-memory dictionary.
# In a production environment, this would be a persistent store like Redis.

class SharedMemory:
    def __init__(self):
        self._memory = {}

    def set(self, key: str, value: str):
        """Stores a value in memory."""
        self._memory[key] = value

    def get(self, key: str) -> str:
        """Retrieves a value from memory."""
        return self._memory.get(key)

    def delete(self, key: str):
        """Deletes a value from memory."""
        if key in self._memory:
            del self._memory[key]

    def clear_session(self, request_id: str):
        """Clears all entries related to a specific request_id."""
        keys_to_delete = [key for key in self._memory if key.startswith(request_id)]
        for key in keys_to_delete:
            del self._memory[key]

shared_memory = SharedMemory()

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

    def clear_session(self, request_id: str, preserve_query: bool = False):
        """
        Clears all entries related to a specific request_id.
        
        Args:
            request_id: The ID of the session to clear.
            preserve_query: If True, the original query for the session will not be deleted.
        """
        query_key = f"{request_id}:query"
        keys_to_delete = []
        for key in self._memory:
            if key.startswith(request_id):
                if preserve_query and key == query_key:
                    continue
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._memory[key]

shared_memory = SharedMemory()

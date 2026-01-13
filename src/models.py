from uagents import Model
from typing import Optional
import uuid

class Query(Model):
    text: str
    request_id: str = ""
    original_sender: Optional[str] = None

    def __init__(self, **data):
        # This allows Pydantic to initialize the model first
        super().__init__(**data)
        # Then, if request_id was not provided, we generate one.
        # This ensures that IDs are created on instantiation but preserved during deserialization.
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
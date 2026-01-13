from uagents import Model
from typing import Optional
import uuid

class Query(Model):
    text: str
    request_id: str = ""
    original_sender: Optional[str] = None
    original_question: Optional[str] = None # New field to track the context

    def __init__(self, **data):
        super().__init__(**data)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
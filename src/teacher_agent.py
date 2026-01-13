from uagents import Agent, Context

from .models import Query
from .avatar import Avatar
from .kb import KnowledgeBase

# Pass only the logical name
teacher_kb = KnowledgeBase("teacher")
teacher_brain = Avatar("Expert Professor")
teacher = Agent(name="teacher", port=8000, seed="teacher_v3_seed")

@teacher.on_message(model=Query)
async def handle_teach(ctx: Context, sender: str, msg: Query):
    ans = teacher_brain.think(teacher_kb.read(), f"Provide the factual answer for: {msg.text}")
    
    if ans == "[MISSING]":
        ans = "I'm sorry, I don't have that information in my expert database."

    # Prepend "Teacher says:" to make it clear who the source is, if desired, 
    # but the user's issue seems to be about wrong answers (Rome -> Paris).
    # The "loosing tags" might refer to the console output not showing "Student:" or "Teacher:".
    # The app.py prints "[RESPONSE] ...".

    await ctx.send(sender, Query(text=ans, original_sender=msg.original_sender, request_id=msg.request_id))
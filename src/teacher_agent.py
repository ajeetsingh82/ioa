from uagents import Agent, Context

from .models import Query
from .avatar import Avatar
from .kb import KnowledgeBase

teacher_kb = KnowledgeBase('./kb/teacher.txt')
teacher_brain = Avatar("Expert Professor")
teacher = Agent(name="teacher", port=8000, seed="teacher_v3_seed")

@teacher.on_message(model=Query)
async def handle_teach(ctx: Context, sender: str, msg: Query):
    ans = teacher_brain.think(teacher_kb.read(), f"Provide the factual answer for: {msg.text}")
    # Return the answer, preserving the original_sender and request_id
    await ctx.send(sender, Query(text=ans, original_sender=msg.original_sender, request_id=msg.request_id))
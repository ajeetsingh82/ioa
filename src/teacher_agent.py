from uagents import Context
from .models import Query
from .avatar import AvatarAgent
from .kb import KnowledgeBase

# Initialize KnowledgeBase
teacher_kb = KnowledgeBase("teacher")

# Create the Teacher Agent with a hierarchical name
teacher = AvatarAgent(
    name="hub.teacher", # Updated namespace
    port=8000,
    seed="teacher_v3_seed",
    persona="Expert Professor",
    domain="expert_knowledge",
    capabilities=["teach", "provide_facts"]
)

@teacher.on_message(model=Query)
async def handle_teach(ctx: Context, sender: str, msg: Query):
    ans = teacher.brain.think(teacher_kb.read(), f"Provide the factual answer for: {msg.text}")
    
    if ans == "[MISSING]":
        ans = "I'm sorry, I don't have that information in my expert database."

    await ctx.send(sender, Query(text=ans, original_sender=msg.original_sender, request_id=msg.request_id))
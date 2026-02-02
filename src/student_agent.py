from uagents import Context
from .avatar import AvatarAgent
from .kb import KnowledgeBase
from .models import Query
from .registry import registry_service

# Initialize KnowledgeBase
student_kb = KnowledgeBase("student")

# Create the Student Agent with a hierarchical name
student = AvatarAgent(
    name="hub.student",
    port=8001,
    seed="student_v3_seed",
    persona="Curious Student",
    domain="general_knowledge",
    capabilities=["ask_questions", "learn", "answer_questions"]
)

@student.on_message(model=Query)
async def handle_message(ctx: Context, sender: str, msg: Query):
    # 1. LEARNING MODE (From Teacher)
    # Resolve sender name
    sender_name = ""
    for agent in registry_service.list_all():
        if agent['address'] == sender:
            sender_name = agent['name']
            break
    
    # Check if the sender is part of the teacher namespace (e.g., hub.teacher, hub.teacher.math)
    # We treat any agent containing 'teacher' in its hierarchy as a valid teacher
    is_teacher = "teacher" in sender_name and sender_name.startswith("hub.")
    
    if is_teacher:
        student_kb.append(msg.text)
        print(f"\n[Learning] Student added to memory (from {sender_name}): {msg.text}")

        if msg.original_sender:
            await ctx.send(msg.original_sender, Query(text=msg.text, request_id=msg.request_id))
        return

    # 2. THINKING MODE (From User/Gateway)
    notes = student_kb.read()

    goal = f"Answer the question '{msg.text}'. Use ONLY the provided context. If the answer is not explicitly in the context, say [MISSING]."
    reply = student.brain.think(notes, goal)

    if reply == "[MISSING]":
        print(f"Student: I don't know that. Asking Teacher Subnet...")
        
        # Dynamic Discovery: Broadcast to the 'hub.teacher' subnet
        teachers = registry_service.find_subnet("hub.teacher")
        
        if teachers:
            target_address = teachers[0]['address']
            await ctx.send(target_address, Query(text=msg.text, original_sender=sender, request_id=msg.request_id))
        else:
            print("No teachers found in subnet 'hub.teacher'")

    else:
        await ctx.send(sender, Query(text=reply, request_id=msg.request_id))
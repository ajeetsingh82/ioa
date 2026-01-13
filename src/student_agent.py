from uagents import Agent, Context
from .avatar import Avatar
from .kb import KnowledgeBase
from .models import Query  # Use the shared model

student_kb = KnowledgeBase('./kb/student.txt')
student_brain = Avatar("Curious Student")
student = Agent(name="student", port=8001, seed="student_v3_seed")

# app.py will overwrite this with teacher.address
TEACHER_ADDRESS = ""

@student.on_message(model=Query)
async def handle_message(ctx: Context, sender: str, msg: Query):
    # 1. LEARNING MODE (From Teacher)
    if sender == TEACHER_ADDRESS:
        student_kb.append(msg.text)
        print(f"\n[Learning] Student added to memory: {msg.text}")

        # Send the answer back to the original user using the info from the message
        if msg.original_sender:
            await ctx.send(msg.original_sender, Query(text=msg.text, request_id=msg.request_id))
        return

    # 2. THINKING MODE (From User/Gateway)
    notes = student_kb.read()

    goal = f"Answer the question '{msg.text}' using context. If missing, say 'MISSING'."
    reply = student_brain.think(notes, goal)

    if "MISSING" in reply.upper():
        print(f"Student: I don't know that. Asking Teacher...")
        # Ask Teacher, passing the current sender as the original_sender
        await ctx.send(TEACHER_ADDRESS, Query(text=msg.text, original_sender=sender, request_id=msg.request_id))
    else:
        # Reply immediately if found in memory
        await ctx.send(sender, Query(text=reply, request_id=msg.request_id))
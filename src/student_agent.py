from uagents import Agent, Context
from .avatar import Avatar
from .kb import KnowledgeBase
from .models import Query  # Use the shared model

# Pass only the logical name
student_kb = KnowledgeBase("student")
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
            # We can optionally include the original question in the response text or just rely on the user knowing context
            # But to fix the "loosing tags" issue, let's make sure the response is clear.
            # The user's log shows "[RESPONSE] Paris." which is coming from app.py.
            # The issue described is that the answer seems wrong ("Rome" -> "Paris").
            # This is likely because the Student is finding "Paris" in its notes and thinking it answers "Rome".
            
            await ctx.send(msg.original_sender, Query(text=msg.text, request_id=msg.request_id))
        return

    # 2. THINKING MODE (From User/Gateway)
    notes = student_kb.read()

    # Improve the goal to be very specific to avoid hallucinating answers from unrelated notes
    goal = f"Answer the question '{msg.text}'. Use ONLY the provided context. If the answer is not explicitly in the context, say [MISSING]."
    reply = student_brain.think(notes, goal)

    # Check for the specific token
    if reply == "[MISSING]":
        print(f"Student: I don't know that. Asking Teacher...")
        # Ask Teacher, passing the current sender as the original_sender AND the question
        await ctx.send(TEACHER_ADDRESS, Query(text=msg.text, original_sender=sender, request_id=msg.request_id))
    else:
        # Reply immediately if found in memory
        await ctx.send(sender, Query(text=reply, request_id=msg.request_id))
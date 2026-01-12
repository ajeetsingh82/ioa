import threading, queue, time, os
from uagents import Agent, Context, Bureau
from src.models import Query
from src.student_agent import student
from src.teacher_agent import teacher
import src.student_agent as student_module

# The 'gateway' is the agent representing YOU (the user)
gateway = Agent(name="gateway", port=8002, seed="gateway_seed")
user_input_queue = queue.Queue()

@gateway.on_interval(period=1.0)
async def send_to_student(ctx: Context):
    try:
        msg = user_input_queue.get_nowait()
        # Gateway sends to Student
        await ctx.send(student.address, Query(text=msg))
    except queue.Empty:
        pass

@gateway.on_message(model=Query)
async def display_reply(ctx: Context, sender: str, msg: Query):
    # This only triggers when the Student sends a message BACK to the gateway
    print(f"\n[RESPONSE] {msg.text}")
    print(">> ", end="", flush=True)

def console():
    time.sleep(3)
    print("\n--- DISTRIBUTED SYSTEM READY ---")
    while True:
        msg = input(">> ")
        if msg.lower() in ['exit', 'quit']: os._exit(0)
        user_input_queue.put(msg)

if __name__ == "__main__":
    # Crucial: Link the student to the teacher before starting
    student_module.TEACHER_ADDRESS = teacher.address

    bureau = Bureau(port=8000)
    bureau.add(teacher)
    bureau.add(student)
    bureau.add(gateway) # Add the gateway to the bureau

    threading.Thread(target=console, daemon=True).start()
    bureau.run()
import requests, os, threading, logging, queue, time
from uagents import Agent, Context, Model, Bureau

logging.getLogger("uagents").setLevel(logging.ERROR)

KB_DIR = '/kb'
KB_TEACHER = os.path.join(KB_DIR, 'teacher.txt')
KB_STUDENT = os.path.join(KB_DIR, 'student.txt')

user_input_queue = queue.Queue()

class Query(Model):
    text: str

def ask_llm(persona, context, goal):
    url = "http://localhost:11434/api/generate"
    prompt = f"""### ROLE: {persona}
### CONTEXT:
{context[-3000:]}

### TASK: {goal}
### REQUIREMENT: Answer in plain English. If info is missing, say 'MISSING'.

### RESPONSE:"""
    try:
        r = requests.post(url, json={"model": "llama3.2:1b", "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get('response', "").strip()
    except Exception as e:
        return "Offline."

teacher = Agent(name="teacher", port=8000, seed="teacher_persistent_seed")
student = Agent(name="student", port=8001, seed="student_persistent_seed")

@teacher.on_message(model=Query)
async def teach(ctx: Context, sender: str, msg: Query):
    with open(KB_TEACHER, 'r') as f:
        kb_content = f.read()
    answer = ask_llm("Expert Teacher", kb_content, f"Direct fact for: {msg.text}")
    await ctx.send(sender, Query(text=answer))

@student.on_interval(period=1.0)
async def process_cli_input(ctx: Context):
    try:
        user_msg = user_input_queue.get_nowait()

        # --- COMMAND: FORGET ---
        if user_msg.startswith("!forget"):
            with open(KB_STUDENT, 'w') as f:
                f.write(f"--- student.txt RESET AT {time.ctime()} ---\n")
            print(f"\n[SYSTEM] Student memory has been cleared.\n>> ", end="", flush=True)
            return

        with open(KB_STUDENT, 'r') as f:
            my_notes = f.read()

        # --- COMMAND: SUMMARY ---
        if user_msg.startswith("!summary"):
            summary = ask_llm("Student", my_notes, "Give me a 3-bullet point summary of the facts you have learned.")
            print(f"\n[STUDENT PROGRESS REPORT]\n{summary}\n\n>> ", end="", flush=True)
            return

        # Standard Memory Check
        student_reply = ask_llm("Student", my_notes, f"Find the answer to '{user_msg}' in your notes. If not there, say 'MISSING'.")

        if "MISSING" in student_reply.upper() or len(student_reply) < 3:
            print(f"Student: I don't know that yet. Asking Teacher...")
            await ctx.send(teacher.address, Query(text=user_msg))
        else:
            print(f"Student (Memory): {student_reply}\n>> ", end="", flush=True)

    except queue.Empty:
        pass

@student.on_message(model=Query)
async def learn(ctx: Context, sender: str, msg: Query):
    clean_fact = msg
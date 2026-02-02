import requests
from uagents import Agent, Context
from .models import Query
from .google_search import search_web

def think(context: str, goal: str) -> str:
    """A simplified 'brain' for the RAG agent, calling the LLM."""
    url = "http://localhost:11434/api/generate"
    prompt = f"""### CONTEXT:
{context}

### TASK:
{goal}

### INSTRUCTIONS:
- Answer the TASK based ONLY on the CONTEXT provided.
- Be concise and direct.
- If the context does not contain the answer, state that clearly.

### RESPONSE:"""
    try:
        r = requests.post(url, json={"model": "llama3.2:1b", "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get('response', "").strip()
    except requests.exceptions.RequestException as e:
        return f"LLM is offline or encountered an error: {e}"

# Create the RAG Agent
rag_agent = Agent(name="rag_agent", port=8004, seed="rag_agent_seed")

@rag_agent.on_message(model=Query)
async def handle_rag_query(ctx: Context, sender: str, msg: Query):
    """
    Handles a query by performing the RAG workflow.
    """
    ctx.logger.info(f"RAG Agent received query: '{msg.text}'")
    
    # 1. Retrieve: Get context from the Web
    retrieved_text = search_web(msg.text)
    ctx.logger.info(f"Retrieved context (first 100 chars): '{retrieved_text[:100]}...'")
    
    # 2. Augment: The goal is now just the user's original question.
    # This simplification helps smaller LLMs focus on the task.
    goal = msg.text
    
    # 3. Generate: Use the LLM to generate a response
    answer = think(context=retrieved_text, goal=goal)
    
    # Send the answer back to the original sender
    await ctx.send(sender, Query(text=answer))
# src/avatar.py
import requests

class Avatar:
    def __init__(self, persona, model="llama3.2:1b"):
        self.persona = persona
        self.model = model

    def think(self, context, goal):
        url = "http://localhost:11434/api/generate"
        # We simplify the prompt: No more "Requirements" section which confuses 1B
        prompt = f"""### CONTEXT: {context}
### TASK: {goal}
### RULES:
- Use context ONLY.
- Be extremely brief (under 10 words).
- No chat, no 'I am happy to help'.
- If info missing, say 'MISSING'.

### RESPONSE:"""

        try:
            r = requests.post(url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=30)
            return r.json().get('response', "").strip()
        except:
            return "Offline."
# src/avatar.py
import requests

class Avatar:
    def __init__(self, persona, model="llama3.2:1b"):
        self.persona = persona
        self.model = model

    def think(self, context, goal):
        url = "http://localhost:11434/api/generate"
        
        prompt = f"""### CONTEXT:
{context}

### TASK:
{goal}

### INSTRUCTIONS:
- You are {self.persona}.
- Answer based ONLY on the CONTEXT provided above.
- If the answer is not in the CONTEXT, output exactly: [MISSING]
- Do not add any conversational filler like "Here is the answer".
- Keep the answer concise (under 20 words).

### RESPONSE:"""

        try:
            r = requests.post(url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=30)
            response_text = r.json().get('response', "").strip()
            
            # Cleanup: sometimes models add extra quotes or spaces
            if "[MISSING]" in response_text:
                return "[MISSING]"
            
            return response_text
        except:
            return "Offline."
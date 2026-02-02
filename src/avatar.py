# src/avatar.py
import requests
from uagents import Agent, Context
from typing import List
from .registry import registry_service

class Avatar:
    """The 'brain' of an agent, responsible for thinking via an LLM."""
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
            
            if "[MISSING]" in response_text:
                return "[MISSING]"
            
            return response_text
        except:
            return "Offline."

class AvatarAgent(Agent):
    """An agent that has an Avatar 'brain' and is self-registering."""
    def __init__(
        self, 
        name: str, 
        port: int, 
        seed: str, 
        persona: str,
        domain: str,
        capabilities: List[str],
        **kwargs
    ):
        super().__init__(name=name, port=port, seed=seed, **kwargs)
        self.brain = Avatar(persona)
        self.domain = domain
        self.capabilities = capabilities
        self._agent_record = None  # To store our record from the registry

    @Agent.on_event("startup")
    async def register_agent(self, ctx: Context):
        """Register the agent with the registry service on startup."""
        record = registry_service.register(
            name=self.name,
            agent_type="AvatarAgent",
            address=ctx.address,
            domain=self.domain,
            capabilities=self.capabilities
        )
        self._agent_record = record
        ctx.logger.info(f"Registered as '{self.name}' with ID: {record['id']}")

    @Agent.on_interval(period=60.0)
    async def send_heartbeat(self, ctx: Context):
        """Send a heartbeat to the registry to stay alive."""
        if self._agent_record:
            if registry_service.heartbeat(self._agent_record['id']):
                ctx.logger.info("Sent heartbeat to registry.")
            else:
                # This can happen if the registry was cleared or restarted
                ctx.logger.warning("Heartbeat failed. Re-registering...")
                self.register_agent(ctx)

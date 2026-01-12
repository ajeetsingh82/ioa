def get_prompt(role, context, goal):
    return f"""### ROLE: {role}
### CONTEXT:
{context}

### TASK: {goal}
### REQUIREMENT: Answer in plain English. No other languages.

### RESPONSE:"""
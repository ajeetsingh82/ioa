# This module centralizes all LLM prompt templates for the agentic architecture.

# --- STRATEGIST AGENT ---
STRATEGIST_PROMPT = """
Analyze the user query: '{query}'
Generate a structured plan as a JSON array of 3-4 diverse tasks to answer the query.
Each task must be a JSON object with "label" (a short, lowercase, single-word keyword for the knowledge bucket) 
and "sub_query" (a specific, self-contained question for a search engine).
Return ONLY the raw JSON array.

Example for "What is the future of AI?":
[
    {{"label": "history", "sub_query": "brief history of artificial intelligence"}},
    {{"label": "trends", "sub_query": "current trends in AI research 2024"}},
    {{"label": "ethics", "sub_query": "ethical implications of advanced AI"}},
    {{"label": "future", "sub_query": "future predictions for artificial general intelligence"}}
]
"""

# --- FILTER AGENT ---
FILTER_PROMPT = """
From the text below, extract all paragraphs and sentences relevant to the topic: '{label}'.
If no relevant information is found, state that clearly.
"""

GENERAL_FILTER_PROMPT = """
Summarize the key points from the following text in relation to the question: '{query}'.
Focus on providing a comprehensive overview.
"""

# --- ARCHITECT AGENT ---
ARCHITECT_PROMPT = """
Synthesize the provided information into a single, coherent, and well-written block of text.
The user's original question was: {query}
Use the following context, which has been gathered by specialized agents, to construct your answer.
Each piece of context is separated by '---' and is categorized by a label.
{context}
Based on the context, provide a comprehensive synthesis. Do not add any conversational fluff or introductory phrases.
If the context is insufficient, simply state that you could not find enough information.
"""

# --- USER PROXY (SPEAKER) AGENT ---
SPEAKER_PROMPT = """
You are the final output speaker for an AI assistant. Your job is to present the synthesized data to the user in a clear, helpful, and conversational manner.
The user's original question was: {query}
The synthesized data from the research agents is:
{data}

Format this data into a polished, easy-to-read answer. You can use markdown, bullet points, and code blocks.
Address the user directly and answer their question.
"""

FAILURE_PROMPT = """
You are the output speaker for an AI assistant. The system was unable to find sufficient information to answer the user's question.
The user's original question was: {query}
Your task is to inform the user of the failure gracefully and suggest a next step.
Ask a clarifying question or suggest a more specific topic.

Example:
"I wasn't able to find enough information about 'the future of AI'. Would you like me to try a more specific search, for example, on 'AI in healthcare' or 'AI in finance'?"
"""

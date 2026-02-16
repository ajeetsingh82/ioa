# Agentic Cognitive Architecture (Local LLM Pipeline)

A graph-ready, agent-based reasoning system running fully on a local
machine using:

-   **Ollama** (local LLM runtime)
-   **uAgents** (agent framework)
-   **FastAPI** (web interface)
-   No vector database
-   No external RAG framework

The system decomposes user queries into structured tasks, performs
reasoning and live search through specialized agents, and synthesizes
results into a final Markdown response.

------------------------------------------------------------------------

# System Overview

## Architecture Components

-   **Gateway Agent** -- Entry point for user queries
-   **Strategist Agent** -- Breaks query into structured tasks
-   **Scout Agents** -- Perform search/retrieval
-   **Filter Agents** -- Extract relevant information
-   **Architect Agent** -- Synthesizes structured context
-   **User Proxy Agent** -- Formats final output (Markdown only)
-   **Conductor** -- Orchestrates agent coordination
-   **Web Chat UI** -- User-facing interface

Inner-agent communication: **Strict JSON**\
Final user output: **Strict Markdown**

------------------------------------------------------------------------

# Requirements

-   macOS / Linux
-   Python 3.12
-   Ollama installed
-   Available local ports:
    -   11434 (Ollama)
    -   8000 (Agent Bureau)
    -   8080 (Chat UI)
    -   9000 (Gateway HTTP)

------------------------------------------------------------------------

# Setup Ollama

## 1. Install Ollama

Download from: https://ollama.com/

## 2. Add to PATH and Start Server

``` bash
export PATH=$PATH:/Applications/Ollama.app/Contents/Resources
/Applications/Ollama.app/Contents/Resources/ollama serve
```

### Verify

``` bash
curl http://localhost:11434
```

You should see:

Ollama is running

## 3. Pull Models

``` bash
ollama pull llama3.2:1b
ollama pull llama3.2:3b
```

```
docker compose -f llm/docker-compose.yml up -d
```

```
curl http://localhost:11434/api/generate -d '{
"model": "llama3.2:1b",
"prompt": "Explain quicksort in one sentence.",
"stream": false
}'
```
------------------------------------------------------------------------

# Setup Python Environment

## Reset Virtual Environment (if needed)

``` bash
deactivate
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

``` bash
pip install -r requirements.txt
pip install uagents
```

------------------------------------------------------------------------

# Running the System

## Terminal 1

``` bash
docker compose up --build -d
# Runs on: http://127.0.0.1:8080/
```


## Terminal 2 --- Start Agent Bureau

``` bash
python app.py
```

Expected logs:

-   Agents registering
-   Bureau running on port 8000
-   Gateway HTTP running on port 9000

------------------------------------------------------------------------

# Execution Flow

1.  User submits query via Web UI
2.  Web UI forwards request to Gateway HTTP
3.  Gateway sends UserQuery to Strategist
4.  Strategist returns structured JSON tasks
5. Architect synthesizes structured result
6. User Proxy formats final Markdown
7. Web UI renders Markdown

------------------------------------------------------------------------

# Output Contract

## Internal Communication

All agents (except User Proxy) must return:

{ "answer": ... }

Or valid structured JSON objects.

## Final Output to User

User Proxy must return:

{ "text": "`<strict markdown output>`{=html}" }

Constraints:

-   No JSON schemas
-   No conversational wrappers
-   Markdown only

------------------------------------------------------------------------

# Current Limitations

-   Linear pipeline strategy
-   No confidence scoring
-   No graph-based exploration
-   No adaptive planning
-   No probabilistic reasoning

------------------------------------------------------------------------

# Roadmap: Graph-Based Strategic Cognition

## Design Goal

Replace the linear pipeline with a dynamic reasoning graph.

## Core Concepts

-   Node = Agent execution state
-   Edge = Task transition
-   Weight = Confidence score toward goal
-   Goal = Maximize answer reliability

------------------------------------------------------------------------

# Future Improvements

-   Confidence estimation model
-   Branch pruning
-   Memory persistence across sessions
-   Adaptive strategy refinement
-   Dynamic task generation during execution
-   Failure-aware fallback planning

------------------------------------------------------------------------

# Philosophy

This system demonstrates:

-   Local-first LLM reasoning
-   Agentic decomposition
-   Structured JSON orchestration
-   Markdown-only final contract
-   No vector database dependency

It is not a wrapper framework.\
It is a controllable cognitive pipeline.

------------------------------------------------------------------------

# Development Notes

If something breaks:

-   Ensure Ollama is running on 11434
-   Ensure Gateway is running on 9000
-   Ensure Bureau is running on 8000
-   Verify Python 3.12 environment is active
-   Inspect logs for schema mismatch or JSON contract violations

------------------------------------------------------------------------

# Status

Version: Pipeline Stabilized\
Next Milestone: Graph-Based Strategic Planner

------------------------------------------------------------------------
```
docker system df -v
# rmoves mount
docker-compose down -v
docker rm <redis-container-name>
docker volume ls
docker volume prune
docker stop ollama-llm
docker rm ollama-llm
docker compose down
docker compose logs -f
docker compose logs -f ollama
docker ps -a      
docker logs ollama-llm -f 
docker logs  webcrawler -f
 docker compose stop webcrawler
docker compose up -d --build webcrawler 
```
1. Start Docker Services: In your project root, run ```docker compose up --build```. This will start the ollama and webapp containers.
   - ```docker compose up --build -d```
2. Start Bureau Locally: In a separate terminal, set up your local Python 3.12 environment and run python app.py.
3. Access UI: Open your browser to http://localhost:8080.

--------------------------------------------------------

```
curl -X POST http://localhost:8080/api/result \
-H "Content-Type: application/json" \
-d '{
"text": "This is a test response.",
"request_id": "some-valid-request-id-from-your-app",
"type": -1
}'

url -X POST http://localhost:8011/render \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
  
curl -X POST "http://localhost:8002/crawl" \
     -H "Content-Type: application/json" \
     -d '{
           "urls": ["https://timesofindia.indiatimes.com/"],
           "freshness_window": 3600
         }'
# "urls": ["https://www.wikipedia.org/", "https://timesofindia.indiatimes.com/"],
```

```
import chromadb
client = chromadb.HttpClient(host="localhost", port=8000)
print(client.list_collections())
```


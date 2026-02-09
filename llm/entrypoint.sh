#!/bin/sh
set -e
MODELS="
llama3.2:1b
nomic-embed-text
"

# Start Ollama in background
ollama serve &
PID=$!

echo "Waiting for Ollama..."

until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done

echo "Ollama ready. Pulling models..."

for MODEL in $MODELS; do
  ollama pull "$MODEL"
done

echo "Models pulled."

# Keep server in foreground
wait $PID
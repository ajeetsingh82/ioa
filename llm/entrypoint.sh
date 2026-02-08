#!/bin/sh
set -e

# Start Ollama server in the background
ollama serve &
pid=$!

# Wait for the server to be ready
echo "Waiting for Ollama server to start..."
sleep 5

# Pull the model
echo "Pulling model: llama3.2:1b"
ollama pull llama3.2:1b

# Bring the server process back to the foreground
wait $pid

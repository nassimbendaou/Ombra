#!/bin/bash
# Start Ollama server if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama server..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    echo "Ollama server started"
else
    echo "Ollama server already running"
fi

# Check available models
ollama list 2>/dev/null || echo "No models available"

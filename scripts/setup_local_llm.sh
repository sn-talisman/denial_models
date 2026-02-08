#!/bin/bash
# Setup script for local LLM (Ollama)

set -e

echo "Setting up local LLM with Ollama..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start Ollama service
echo "Starting Ollama service..."
docker-compose up -d ollama

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
sleep 10

# Check if Ollama is responding
if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is ready!"
else
    echo "Warning: Ollama may not be ready yet. Waiting a bit longer..."
    sleep 10
fi

# Pull recommended models
echo "Pulling recommended LLM models..."
echo "This may take several minutes depending on your internet connection..."

ollama pull mistral || echo "Warning: Failed to pull mistral model"
ollama pull llama3 || echo "Warning: Failed to pull llama3 model"

echo ""
echo "Setup complete!"
echo ""
echo "To verify Ollama is working, run:"
echo "  ollama list"
echo ""
echo "To test a model, run:"
echo "  ollama run mistral 'Hello, world!'"


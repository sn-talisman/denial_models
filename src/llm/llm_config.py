"""LLM configuration and model selection."""

import os
from typing import Optional

# Supported models for different tasks
SUPPORTED_MODELS = {
    "classification": ["mistral", "llama3", "gemma"],
    "generation": ["mistral", "llama3", "gemma"],
    "parsing": ["mistral", "llama3"],
}

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
DEFAULT_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
DEFAULT_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "512"))


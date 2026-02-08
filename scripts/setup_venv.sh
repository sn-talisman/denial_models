#!/bin/bash
# Setup virtual environment and install dependencies

set -e

echo "Setting up virtual environment..."

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate venv and upgrade pip
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# Install project dependencies
echo "Installing project dependencies..."
pip install -e ".[dev]"

echo ""
echo "Setup complete! Activate the virtual environment with:"
echo "  source venv/bin/activate"


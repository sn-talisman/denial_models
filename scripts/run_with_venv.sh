#!/bin/bash
# Run a command in the virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run: bash scripts/setup_venv.sh"
    exit 1
fi

source venv/bin/activate

# Run the command passed as arguments
exec "$@"


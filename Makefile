.PHONY: help setup install db-up db-down llm-setup llm-pull ingest test lint serve clean

help:
	@echo "Healthcare Denial Management Platform - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Initial project setup (install dependencies)"
	@echo "  make install        - Install package in development mode"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make db-up          - Start PostgreSQL (if using Docker, otherwise external)"
	@echo "  make db-down        - Stop PostgreSQL (if using Docker)"
	@echo "  make llm-setup      - Setup and pull Ollama models"
	@echo "  make llm-pull       - Pull required LLM models"
	@echo ""
	@echo "Development:"
	@echo "  make ingest         - Run data ingestion pipeline"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linters (ruff, mypy)"
	@echo "  make serve          - Start FastAPI development server"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove generated files and caches"

setup:
	@echo "Setting up virtual environment..."
	@if [ ! -d "venv" ]; then \
		python3 -m venv venv; \
		echo "Virtual environment created"; \
	else \
		echo "Virtual environment already exists"; \
	fi
	@. venv/bin/activate && pip install --upgrade pip setuptools wheel
	@. venv/bin/activate && pip install -e ".[dev]"
	@echo "Setup complete! Activate virtual environment with: source venv/bin/activate"

install:
	pip install -e ".[dev]"

db-up:
	@echo "Note: PostgreSQL should be running externally on localhost:5432"
	@echo "If you need to start PostgreSQL via Docker, add a service to docker-compose.yml"

db-down:
	@echo "Note: PostgreSQL is external. Stop it manually if needed."

llm-setup:
	docker-compose up -d ollama
	@echo "Waiting for Ollama to be ready..."
	@sleep 5
	@echo "Ollama is ready. Run 'make llm-pull' to download models."

llm-pull:
	@echo "Pulling Ollama models..."
	ollama pull mistral
	ollama pull llama3
	@echo "Models pulled successfully."

ingest:
	python scripts/run_pipeline.py ingest

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	ruff check src tests scripts
	mypy src --ignore-missing-imports

serve:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	rm -rf .ruff_cache
	@echo "Cleanup complete."


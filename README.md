# Healthcare Denial Management Platform

An intelligent platform that uses machine learning to analyze healthcare claim denials and predict denial risk for new claims, providing actionable recommendations to reduce denial rates.

## 🏗️ Architecture

The platform is built with a clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    API Service Layer                         │
│              (FastAPI - Predictions & Analytics)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    ML Models Layer                            │
│  (Denial Predictor, Reason Classifier, Explainability)       │
└──────────────────────┬────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Data Engineering Pipelines                       │
│  (Ingestion → Normalization → Feature Engineering)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Data Access Layer                           │
│         (Repository Pattern - DB or FHIR)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼────────┐          ┌─────────▼─────────┐
│  PostgreSQL    │          │  HAPI FHIR Server │
│  (Current)     │          │   (Future)        │
└────────────────┘          └───────────────────┘
```

### Key Principles

1. **Separation of Concerns**: Clear boundaries between data access, pipelines, models, and API
2. **Data Access Abstraction**: Repository pattern allows switching between database and FHIR without changing other layers
3. **Local-Only Processing**: All LLM inference runs locally via Ollama - no PHI leaves the environment
4. **HIPAA Compliance**: PHI redaction in logs, structured error handling, no external API calls

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (running on localhost:5432)
- Docker (for Ollama LLM service)
- Make (optional, for convenience commands)

### Setup

1. **Clone and navigate to project:**
   ```bash
   cd healthcare-denial-management
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   make setup
   # Or manually:
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

4. **Discover database schema:**
   ```bash
   python scripts/introspect_db.py
   ```
   This will generate `docs/database_schema.md` with the discovered schema.

5. **Setup local LLM:**
   ```bash
   make llm-setup
   make llm-pull
   ```

6. **Run tests:**
   ```bash
   make test
   ```

## 📁 Project Structure

```
healthcare-denial-management/
├── src/
│   ├── data_access/          # Repository pattern for data access
│   ├── pipelines/             # ETL and feature engineering
│   ├── models/                # ML models (Phase 2)
│   ├── analytics/             # Root cause analysis (Phase 2)
│   ├── llm/                   # Local LLM client (Ollama)
│   ├── api/                   # FastAPI service (Phase 2)
│   └── utils/                 # Logging, metrics, constants
├── config/                    # YAML configuration files
├── tests/                     # Test suite
├── scripts/                   # Utility scripts
├── notebooks/                 # Jupyter notebooks for EDA
└── docs/                     # Documentation
```

## 🔧 Configuration

### Environment Variables

Key environment variables (see `.env.example`):

- `DATABASE_URL`: PostgreSQL connection string
- `REPOSITORY_TYPE`: "database" or "fhir" (future)
- `OLLAMA_BASE_URL`: Ollama service URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model name (default: mistral)
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)
- `REDACT_PHI_IN_LOGS`: Enable PHI redaction (default: true)

### Configuration Files

- `config/settings.yaml`: Global application settings
- `config/denial_taxonomy.yaml`: Denial reason taxonomy mapping
- `config/feature_registry.yaml`: Feature definitions and modifiability flags

## 🧪 Development

### Running Tests

```bash
make test              # Run all tests
pytest tests/unit/     # Run unit tests only
pytest tests/integration/  # Run integration tests
```

### Linting

```bash
make lint              # Run ruff and mypy
ruff check src/        # Check code style
```

### Running Pipeline

```bash
make ingest            # Run ingestion pipeline
python scripts/run_pipeline.py ingest --days-back 30
```

### Starting API Server

```bash
make serve             # Start FastAPI dev server
uvicorn src.api.app:app --reload
```

## 📊 Phase 1 Status

✅ **Completed:**
- Project structure and configuration
- Data access layer (repository pattern, Pydantic models)
- Database repository stub (ready for schema mapping)
- LLM client for local inference
- Denial taxonomy normalization
- Ingestion pipeline with schema validation
- Logging with PHI redaction
- Basic tests

🚧 **In Progress:**
- Database schema introspection and mapping
- Complete database repository implementation

📋 **Phase 2 (Future):**
- Feature engineering pipeline
- ML model training and inference
- Root cause analysis
- API endpoints
- SHAP explanations
- Counterfactual recommendations

## 🔒 Security & Compliance

- **HIPAA Compliance**: All PHI is redacted in logs
- **Local Processing**: No data or model calls leave the local environment
- **No External APIs**: LLM inference runs via local Ollama instance
- **Structured Logging**: PHI-safe logging with field redaction

## 📝 Database Schema Discovery

Before using the platform, you must:

1. **Connect to your database** and ensure credentials are correct in `.env`
2. **Run schema introspection:**
   ```bash
   python scripts/introspect_db.py
   ```
3. **Review generated schema** in `docs/database_schema.md`
4. **Update repository implementation** in `src/data_access/db_repository.py` to map actual tables

The repository currently has stub implementations that return empty results. After schema discovery, update the SQL queries to match your actual table structure.

## 🤝 Contributing

This is a proprietary project. Follow these guidelines:

1. Maintain separation of concerns
2. Use type hints everywhere
3. Write tests for new functionality
4. Follow HIPAA compliance practices
5. Document any database schema assumptions

## 📄 License

Proprietary - All rights reserved

## 🆘 Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `psql -h localhost -U postgres -d tebra`
- Check `DATABASE_URL` in `.env` matches your credentials
- Ensure asyncpg driver is in connection string: `postgresql+asyncpg://...`

### Ollama Not Responding

- Check Docker is running: `docker ps`
- Verify Ollama container: `docker-compose ps`
- Test Ollama: `curl http://localhost:11434/api/tags`
- Restart: `docker-compose restart ollama`

### Import Errors

- Ensure virtual environment is activated
- Install package: `pip install -e .`
- Check Python version: `python --version` (should be 3.11+)

## 📚 Additional Resources

- [Database Schema Documentation](docs/database_schema.md)
- [Denial Taxonomy](config/denial_taxonomy.yaml)
- [Feature Registry](config/feature_registry.yaml)


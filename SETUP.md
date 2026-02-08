# Setup Instructions

## Initial Setup

1. **Create `.env` file:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```
   
   If `.env.example` doesn't exist, create `.env` with:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tebra
   REPOSITORY_TYPE=database
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=mistral
   LOG_LEVEL=INFO
   REDACT_PHI_IN_LOGS=true
   ```

2. **Install dependencies:**
   ```bash
   make setup
   # Or:
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Discover database schema:**
   ```bash
   python scripts/introspect_db.py
   ```
   
   This will generate `docs/database_schema.md`. **Important:** After schema discovery, you must update `src/data_access/db_repository.py` to map actual table names and columns.

4. **Setup local LLM:**
   ```bash
   make llm-setup
   make llm-pull
   ```

## Next Steps After Schema Discovery

1. **Update Database Repository:**
   - Review `docs/database_schema.md`
   - Update `src/data_access/db_repository.py` with actual SQL queries
   - Map discovered columns to Pydantic models in `src/data_access/models.py`
   - Test with: `pytest tests/unit/test_data_access.py`

2. **Test Data Access:**
   ```bash
   python -c "
   import asyncio
   from src.data_access.factory import get_repository
   async def test():
       repo = get_repository()
       claims = await repo.get_claims(limit=10)
       print(f'Found {len(claims)} claims')
       await repo.close()
   asyncio.run(test())
   ```

3. **Run Pipeline:**
   ```bash
   python scripts/run_pipeline.py ingest --days-back 30
   ```

## Troubleshooting

### Database Connection
- Verify PostgreSQL is running: `psql -h localhost -U postgres -d tebra`
- Check credentials in `.env`
- Ensure connection string uses `postgresql+asyncpg://` format

### Ollama
- Check Docker: `docker ps`
- Verify Ollama: `curl http://localhost:11434/api/tags`
- Restart: `docker-compose restart ollama`


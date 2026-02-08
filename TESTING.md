# Testing Guide

## Setup Virtual Environment

First, set up the virtual environment and install dependencies:

```bash
# Option 1: Use the Makefile
make setup

# Option 2: Use the setup script
bash scripts/setup_venv.sh

# Option 3: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

## Test Database Repository

Once dependencies are installed, test the repository:

```bash
# Activate virtual environment
source venv/bin/activate

# Set database URL (or use .env file)
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"

# Run repository test
python scripts/test_repository.py
```

Or use the convenience script:

```bash
bash scripts/run_with_venv.sh python scripts/test_repository.py
```

## Run Ingestion Pipeline

Test the full ingestion pipeline:

```bash
# Activate virtual environment
source venv/bin/activate

# Set database URL
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"

# Run ingestion
python scripts/run_pipeline.py ingest --days-back 30 --limit 100
```

## Run Unit Tests

```bash
source venv/bin/activate
pytest tests/unit/ -v
```

## Expected Output

### Repository Test
The test should show:
- Number of practices found
- Number of payers found
- Sample claims with details
- Line items for claims
- Denial details (if any)
- Historical denial rates

### Ingestion Pipeline
The pipeline should:
- Fetch claims from database
- Validate schema
- Convert to DataFrame
- Log progress

## Troubleshooting

### Virtual Environment Issues
If venv creation fails:
```bash
# Remove existing venv and recreate
rm -rf venv
python3 -m venv venv
```

### Database Connection Issues
Verify connection:
```bash
psql -h localhost -U tebra_user -d tebra_dw
```

### Import Errors
Ensure you're in the virtual environment:
```bash
which python  # Should show venv/bin/python
```

### Missing Dependencies
Reinstall:
```bash
source venv/bin/activate
pip install -e ".[dev]"
```


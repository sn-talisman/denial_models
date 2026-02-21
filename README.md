# Healthcare Denial Management Platform

An intelligent platform that uses machine learning to predict, analyze, and reduce healthcare claim denials. Built on a PostgreSQL data warehouse of Tebra practice management data, it provides a REST API for real-time denial prediction, root-cause analytics, and actionable practice-level insights.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Installation & Setup](#installation--setup)
6. [Configuration Reference](#configuration-reference)
7. [Database Schema & Data Model](#database-schema--data-model)
8. [Feature Engineering Pipeline](#feature-engineering-pipeline)
9. [Model Training](#model-training)
10. [Running the API Server](#running-the-api-server)
11. [API Endpoints Overview](#api-endpoints-overview)
12. [Generating Practice Insight Reports](#generating-practice-insight-reports)
13. [Testing](#testing)
14. [Development Workflow](#development-workflow)
15. [Denial Classification Logic](#denial-classification-logic)
16. [Troubleshooting](#troubleshooting)

---

## Overview

Healthcare claim denials represent a significant revenue-cycle challenge. This platform addresses denials from end to end:

| Capability | Description |
|---|---|
| **Denial Prediction** | A calibrated LightGBM model predicts denial probability for each claim, classifying risk as low / medium / high. |
| **Root-Cause Analysis** | CARC/RARC code aggregation, CPT-CARC correlation, and rejection pattern detection surface the *why* behind denials. |
| **Practice Analytics** | Per-practice performance summaries, payer breakdowns, CPT breakdowns, high-risk claim lists, and prioritized action items. |
| **System-Wide Insights** | Cross-practice aggregation reveals the top denial reasons, worst-performing payers, and total recovery potential. |
| **Report Generation** | A script consumes the API to produce a rich Markdown report (`PRACTICE_INSIGHTS.md`) for each practice. |

### Latest Model Performance (Feb 2026)

| Metric | Training | Validation |
|---|---|---|
| Precision | 1.0000 | 1.0000 |
| Recall | 0.9956 | 0.9920 |
| F1 Score | 0.9978 | 0.9960 |
| ROC AUC | 1.0000 | 0.9985 |
| Accuracy | 0.9968 | 0.9942 |
| Brier Score | 0.0023 | 0.0055 |

Trained on **12,172 claims** with **1,798 engineered features** across **21 practices** and **26 providers**.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                          │
│  Routes: health, predictions, analytics_aggregate,                 │
│          analytics_practice, analytics_overall                     │
│  Schemas: Pydantic request / response models                       │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│                      Service Layer                                 │
│  analytics_service       — performance summaries, action items     │
│  denial_analysis_service — CARC/RARC aggregation, CPT-CARC corr.  │
│  rejection_analysis_service — missing-field detection per CPT     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│                     ML Models Layer                                 │
│  DenialPredictor  — inference (predict / predict_batch)            │
│  Trainer          — training (LightGBM / XGBoost + Optuna)         │
│  Calibration      — isotonic calibration of probabilities          │
│  Explainability   — SHAP-based feature importance                  │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│               Feature Engineering Pipelines                        │
│  claim_features, temporal_features, historical_features,           │
│  cpt_carc_interactions, rejection_patterns, code_encoders          │
│  Orchestrator: feature_engineer_optimized (async batching + cache) │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│                   Data Access Layer                                 │
│  ClaimsRepository (abstract)  ←  DatabaseClaimsRepository (impl)   │
│  Factory: get_repository() — selects impl based on env config      │
│  Models: Claim, ClaimLineItem, DenialDetail, Practice, Payer, etc. │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               │                             │
        ┌──────▼───────┐          ┌──────────▼──────────┐
        │  PostgreSQL   │          │  HAPI FHIR Server   │
        │  (tebra_dw)   │          │  (future)           │
        └──────────────┘          └─────────────────────┘
```

### Key Design Principles

1. **Repository Pattern** — All data access goes through `ClaimsRepository`. Switching from PostgreSQL to FHIR requires only a new implementation, no changes to services, models, or API.
2. **Async I/O** — SQLAlchemy asyncpg driver and `asyncio.gather` for parallel batch fetching of line items and denial details.
3. **Feature Caching** — The optimized feature engineer pre-fetches historical denial rates for all unique CPT-payer, practice, and provider combinations, avoiding per-claim DB round-trips.
4. **Service Separation** — Business logic lives in `src/services/`, keeping API routes thin.
5. **Pydantic Everywhere** — Data models (`src/data_access/models.py`) and API schemas (`src/api/schemas.py`) both use Pydantic v2 for validation and serialization.

---

## Project Structure

```
denial-models/
├── README.md                          # This file
├── API_DOCUMENTATION.md               # Detailed API endpoint documentation
├── PRACTICE_INSIGHTS.md               # Generated practice insight reports
├── pyproject.toml                     # Project metadata, dependencies, tool config
├── Makefile                           # Convenience commands
├── docker-compose.yml                 # Ollama LLM service
│
├── config/
│   ├── settings.yaml                  # Global application settings
│   ├── denial_taxonomy.yaml           # CARC/RARC → denial category mapping
│   └── feature_registry.yaml          # Feature definitions & modifiability flags
│
├── docs/
│   └── database_schema.md             # Tebra DB schema (auto-generated + annotated)
│
├── models/
│   └── denial_predictor_lightgbm.pkl  # Serialized trained model (pickle)
│
├── scripts/
│   ├── train_model.py                 # Train or retrain the denial model
│   ├── evaluate_model.py              # Evaluate on held-out test set
│   ├── generate_practice_insights_via_api.py  # Generate PRACTICE_INSIGHTS.md via API
│   ├── generate_practice_insights.py  # Generate insights directly (no API)
│   ├── run_pipeline.py                # Run ingestion / feature pipeline
│   ├── introspect_db.py               # Auto-generate database schema docs
│   ├── seed_database.sh               # Seed DB with sample data
│   ├── setup_local_llm.sh             # Configure Ollama
│   └── setup_venv.sh                  # Create virtual environment
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/                           # FastAPI application
│   │   ├── app.py                     # App factory, middleware, router registration
│   │   ├── dependencies.py            # Shared FastAPI dependencies
│   │   ├── schemas.py                 # All Pydantic request/response schemas
│   │   └── routes/
│   │       ├── __init__.py            # Router docstring index
│   │       ├── health.py              # GET /health, GET /ready
│   │       ├── predictions.py         # POST /api/v1/predict, predict/batch, model/info
│   │       ├── analytics_aggregate.py # GET  /api/v1/analytics/practices, payers, practice-payer
│   │       ├── analytics_practice.py  # GET  /api/v1/analytics/practice/{guid}/*
│   │       └── analytics_overall.py   # GET  /api/v1/analytics/overall-insights
│   │
│   ├── services/                      # Business logic layer
│   │   ├── __init__.py
│   │   ├── analytics_service.py       # Practice data retrieval, performance summaries,
│   │   │                              #   payer/CPT breakdowns, action items, aggregate pipeline
│   │   ├── denial_analysis_service.py # CARC/RARC aggregation, CPT-CARC correlation
│   │   └── rejection_analysis_service.py  # Missing-field detection, rejection risk scoring
│   │
│   ├── models/                        # ML model code
│   │   ├── denial_predictor/
│   │   │   ├── predictor.py           # DenialPredictor — load model, predict, predict_batch
│   │   │   ├── trainer.py             # prepare_training_data, train_denial_predictor, save/load
│   │   │   ├── calibration.py         # Probability calibration utilities
│   │   │   └── hyperparameter_tuning.py  # Optuna-based hyperparameter search
│   │   ├── denial_reason_classifier/
│   │   │   ├── taxonomy_classifier.py # Maps denial reasons to taxonomy categories
│   │   │   └── confidence_scorer.py   # Confidence scoring for classifications
│   │   ├── explainability/
│   │   │   ├── shap_explainer.py      # SHAP-based feature importance
│   │   │   ├── counterfactual.py      # Counterfactual explanations
│   │   │   └── modifiability.py       # Which features are actionable
│   │   └── model_registry.py          # Model versioning and registry
│   │
│   ├── pipelines/                     # Data processing pipelines
│   │   ├── pipeline_runner.py         # Orchestrates ingestion → features → output
│   │   ├── ingestion/
│   │   │   ├── claims_ingestion.py    # Fetch claims from repository
│   │   │   └── schema_validation.py   # Pandera schema validation
│   │   ├── normalization/
│   │   │   ├── code_normalization.py  # CPT, ICD-10, modifier, POS normalization
│   │   │   ├── denial_taxonomy.py     # CARC/RARC → denial category mapping
│   │   │   └── llm_classifier.py      # LLM-based free-text classification
│   │   └── feature_engineering/
│   │       ├── feature_engineer_optimized.py  # Async batched feature extraction (primary)
│   │       ├── feature_engineer.py    # Original feature engineer (reference)
│   │       ├── claim_features.py      # Claim-level numeric features
│   │       ├── temporal_features.py   # Date/time-derived features
│   │       ├── historical_features.py # Historical denial rate lookups
│   │       ├── cpt_carc_interactions.py  # CPT × CARC/RARC interaction features
│   │       ├── rejection_patterns.py  # Missing/invalid field indicators
│   │       ├── code_encoders.py       # Target encoding (placeholder)
│   │       ├── patient_features.py    # Patient-level features (placeholder)
│   │       └── practice_features.py   # Practice-level features (placeholder)
│   │
│   ├── data_access/                   # Repository pattern data layer
│   │   ├── models.py                  # Pydantic domain models (Claim, Practice, Payer, etc.)
│   │   ├── base_repository.py         # Abstract ClaimsRepository interface
│   │   ├── db_repository.py           # PostgreSQL implementation (asyncpg)
│   │   ├── fhir_repository.py         # FHIR R4 implementation (stub)
│   │   └── factory.py                 # get_repository() factory function
│   │
│   ├── analytics/                     # Advanced analytics modules
│   │   ├── denial_rate_analysis.py
│   │   ├── confidence_intervals.py
│   │   ├── interaction_effects.py
│   │   ├── pattern_discovery.py
│   │   └── practice_benchmarking.py
│   │
│   ├── llm/                           # Local LLM integration (Ollama)
│   │   ├── llm_client.py             # Async Ollama client
│   │   ├── llm_config.py             # Model selection and config
│   │   └── prompts/                   # Prompt templates
│   │       ├── denial_reason_classification.txt
│   │       ├── explanation_generation.txt
│   │       └── free_text_parsing.txt
│   │
│   └── utils/
│       ├── constants.py               # DenialCategory enum, CARC code lookup, filing deadlines
│       ├── logging_config.py          # Structured logging with PHI redaction
│       └── metrics.py                 # Precision, recall, F1, AUC, Brier, ECE calculations
│
└── tests/
    ├── conftest.py                    # Shared pytest fixtures (claims, mocks, predictions)
    ├── fixtures/
    │   └── sample_claims.json         # Sample claim data for tests
    ├── unit/
    │   ├── test_schemas.py            # Pydantic schema validation tests
    │   ├── test_predictor.py          # DenialPredictor predict/predict_batch tests
    │   ├── test_trainer.py            # Training pipeline tests
    │   ├── test_feature_engineering.py # Feature extraction tests
    │   ├── test_analytics_service.py  # Analytics service function tests
    │   ├── test_data_access.py        # Repository model tests
    │   ├── test_code_normalization.py # Code normalization tests
    │   └── test_denial_taxonomy.py    # Taxonomy mapping tests
    ├── api/
    │   ├── test_app.py                # FastAPI app setup, root, health, openapi tests
    │   ├── test_predictions.py        # Prediction endpoint tests
    │   └── test_analytics_routes.py   # Analytics route tests (all three routers)
    ├── reports/
    │   └── test_insights_report.py    # Practice insight report generation tests
    └── integration/
        └── test_pipeline_end_to_end.py  # End-to-end pipeline tests (requires DB)
```

---

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| PostgreSQL | 14+ | Data warehouse (`tebra_dw` database) |
| Docker | 20+ | Ollama LLM service (optional) |
| Make | any | Convenience commands (optional) |

The PostgreSQL database must contain the Tebra schema tables (see [Database Schema](#database-schema--data-model)).

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/sn-talisman/denial_models.git
cd denial_models
```

### 2. Create a virtual environment and install dependencies

```bash
make setup
# Or manually:
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

This installs all runtime and development dependencies defined in `pyproject.toml`:
- **ML / Data**: pandas, numpy, scikit-learn, lightgbm, xgboost, shap, optuna
- **Validation**: pydantic, pandera
- **API**: fastapi, uvicorn, httpx
- **Database**: sqlalchemy, asyncpg, psycopg2-binary, alembic, greenlet
- **LLM**: ollama
- **Analytics**: scipy, mlxtend
- **Dev**: pytest, pytest-asyncio, pytest-cov, ruff, mypy, black

### 3. Configure environment variables

Create a `.env` file in the project root (or export directly):

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"
REPOSITORY_TYPE="database"
```

See [Configuration Reference](#configuration-reference) for all available variables.

### 4. Verify database connectivity

```bash
python scripts/introspect_db.py
```

This connects to the database, introspects all tables, and generates `docs/database_schema.md`.

### 5. Train the model

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
REPOSITORY_TYPE="database" \
python scripts/train_model.py --days-back 365 --model-type lightgbm
```

See [Model Training](#model-training) for detailed options.

### 6. Start the API server

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001
```

### 7. Run tests

```bash
make test
# Or:
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Configuration Reference

All configuration is via environment variables. A `.env` file in the project root is loaded automatically by `python-dotenv`.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/tebra` | Full SQLAlchemy async connection string. Must use `postgresql+asyncpg://` driver prefix. |
| `REPOSITORY_TYPE` | `database` | Data source type. `database` for PostgreSQL, `fhir` for HAPI FHIR (future). |
| `DENIAL_MODEL_PATH` | `models/denial_predictor_lightgbm.pkl` | Path to the serialized model file used by the API. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama LLM service URL for local inference. |
| `OLLAMA_MODEL` | `mistral` | Default Ollama model for free-text classification. |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `REDACT_PHI_IN_LOGS` | `true` | Enable PHI redaction in structured logs. |
| `FHIR_BASE_URL` | `http://localhost:8080/fhir` | HAPI FHIR server URL (only used when `REPOSITORY_TYPE=fhir`). |
| `PRACTICE_FILTER` | *(none)* | When set, the insight report script only processes practices whose name contains this substring. |

### Configuration Files

| File | Purpose |
|---|---|
| `config/settings.yaml` | Global application settings (thresholds, defaults) |
| `config/denial_taxonomy.yaml` | Maps CARC/RARC code ranges to standardized denial categories (eligibility, coding, medical necessity, etc.) |
| `config/feature_registry.yaml` | Declares all feature names, types, and whether they are modifiable (for counterfactual recommendations) |

---

## Database Schema & Data Model

The platform reads from a PostgreSQL data warehouse (`tebra_dw`) in the `tebra` schema. The full auto-generated schema is in [`docs/database_schema.md`](docs/database_schema.md).

### Core Tables

| Table | Description | Primary Key |
|---|---|---|
| `cmn_practice` | Medical practices / organizations | `practice_guid` (UUID) |
| `cmn_provider` | Healthcare providers (NPI, name) | `provider_guid` (UUID) |
| `cmn_patient` | Patient demographics (PHI) | `patient_guid` (UUID) |
| `cmn_location` | Practice locations (address) | `location_guid` (UUID) |
| `ref_insurance_policy` | Insurance payer/plan info | `policy_key` (VARCHAR) |
| `clin_encounter` | Clinical encounters / appointments | `encounter_id` (BIGINT) |
| `clin_encounter_diagnosis` | ICD-10 diagnoses per encounter | (`encounter_id`, `diag_code`) |
| `fin_claim_line` | Individual claim line items (billing) | `tebra_claim_id` (TEXT) |
| `fin_era_bundle` | Electronic remittance advice (ERA) | `claim_reference_id` (VARCHAR) |
| `fin_era_report` | ERA report metadata | `era_report_id` (TEXT) |

### Key Join Relationships

All practice linkage uses **direct GUID foreign keys** (updated Feb 2026, no fuzzy name matching):

```
fin_claim_line.practice_guid   ──→  cmn_practice.practice_guid
fin_claim_line.encounter_id    ──→  clin_encounter.encounter_id
fin_claim_line.patient_guid    ──→  cmn_patient.patient_guid
clin_encounter.practice_guid   ──→  cmn_practice.practice_guid
clin_encounter.provider_guid   ──→  cmn_provider.provider_guid
clin_encounter.location_guid   ──→  cmn_location.location_guid
clin_encounter.insurance_policy_key ──→ ref_insurance_policy.policy_key
clin_encounter_diagnosis.encounter_id ──→ clin_encounter.encounter_id
```

### Pydantic Domain Models

Defined in `src/data_access/models.py`:

| Model | Key Fields | Notes |
|---|---|---|
| `Claim` | `claim_id`, `practice_id`, `payer_id`, `patient_id`, `provider_id`, `status`, `total_billed_amount`, `total_paid_amount`, `is_secondary_claim`, `has_referral` | Central entity. `status` is a `ClaimStatus` enum. |
| `ClaimLineItem` | `line_item_id`, `claim_id`, `cpt_code`, `modifiers`, `icd10_code`, `billed_amount`, `place_of_service` | One claim has many line items. CPT codes may be formatted as `HC:92507:GN`. |
| `DenialDetail` | `denial_id`, `claim_id`, `carc_code`, `rarc_code`, `adjustment_amount`, `denial_reason_text` | Parsed from `adjustments_json` and `adjustment_descriptions` in `fin_claim_line`. |
| `Practice` | `practice_id`, `name`, `npi` | Maps to `cmn_practice`. |
| `Payer` | `payer_id`, `name`, `plan_type` | Maps to `ref_insurance_policy`. |
| `DenialRateRecord` | `group_key`, `total_claims`, `denied_claims`, `denial_rate` | Aggregated rates for feature engineering. |
| `ClaimStatus` | Enum: `PENDING`, `SUBMITTED`, `PAID`, `DENIED`, `REJECTED`, `APPEALED`, `VOIDED` | Determined by mapping both `claim_status` and `payer_status` fields with a priority hierarchy. |

### Claim Status Mapping

The database stores both `claim_status` (internal workflow) and `payer_status` (payer response). The `_map_claim_status()` method resolves them with this priority:

1. **REJECTED** — if either field contains "rejected"
2. **DENIED** — if either field contains "denied"
3. **PAID** — if `payer_status` contains "paid"
4. **SUBMITTED** — if either field contains "submitted"
5. **PENDING** — default fallback

---

## Feature Engineering Pipeline

The feature engineering pipeline (`src/pipelines/feature_engineering/feature_engineer_optimized.py`) is the heart of the ML system. It transforms raw claims into a feature matrix of ~1,798 columns.

### Pipeline Steps

```
Step 1: Batch Fetch
  └─ asyncio.gather all line_items + denial_details for every claim (parallel)

Step 2: Identify Unique Combinations
  └─ Collect unique (CPT, payer), practice, and provider combos

Step 3: Pre-Fetch Historical Denial Rates
  └─ One bulk query per group_by dimension, cache results

Step 4: Per-Claim Feature Extraction
  └─ For each claim:
       ├─ Claim features (amounts, ratios, line item counts)
       ├─ CPT features (code category, validity flags)
       ├─ Temporal features (day of week, month, submission lag)
       ├─ Denial detail features (CARC/RARC counts, adjustment totals)
       ├─ CPT-CARC interaction features (one-hot combinations)
       ├─ Rejection pattern features (missing field indicators)
       ├─ Historical features (from cache: cpt-payer rate, practice rate, provider rate)
       └─ Denial flag determination (is_denied, is_rejected)
```

### Feature Categories

| Category | Module | Example Features | Count |
|---|---|---|---|
| **Claim-Level** | `claim_features.py` | `total_billed_amount`, `total_paid_amount`, `payment_ratio`, `line_item_count`, `has_modifiers` | ~15 |
| **Temporal** | `temporal_features.py` | `service_day_of_week`, `service_month`, `submission_lag_days`, `days_since_service` | ~10 |
| **Historical Rates** | `historical_features.py` | `hist_denial_rate_cpt_payer`, `hist_denial_rate_practice`, `hist_denial_rate_provider`, 90d/180d/365d windows | ~18 |
| **CPT-CARC Interactions** | `cpt_carc_interactions.py` | `cpt_carc_<code>_<code>` one-hot flags, aggregated interaction counts | ~1,700+ |
| **Rejection Patterns** | `rejection_patterns.py` | `missing_patient_id`, `missing_service_date`, `invalid_cpt_code`, `missing_billed_amount` | ~10 |
| **Denial Details** | (inline in optimized) | `denial_detail_count`, `unique_carc_count`, `unique_rarc_count`, `total_adjustment_from_details` | ~5 |
| **Derived** | (inline in optimized) | `adjustment_amount`, `adjustment_ratio`, `has_partial_denial`, `is_partially_paid` | ~5 |

### Performance Optimization

The optimized pipeline avoids per-claim database queries:

- **Batch fetching**: All line items and denial details are fetched in parallel with `asyncio.gather` at the start.
- **Historical caching**: Historical denial rates are fetched once per unique combination (e.g., 4,216 CPT-payer combos) and cached in a dictionary, avoiding 12,000+ individual queries.
- **Progress logging**: Logs every 5% progress for visibility on long runs.

---

## Model Training

### Quick Start

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
REPOSITORY_TYPE="database" \
python scripts/train_model.py --days-back 365 --model-type lightgbm
```

### Full CLI Options

```
python scripts/train_model.py [OPTIONS]

Options:
  --days-back INT          Number of days of historical data to train on (default: 365)
  --limit INT              Maximum number of claims to use (default: no limit)
  --model-type {xgboost,lightgbm}  Model algorithm (default: lightgbm)
  --tune                   Enable Optuna hyperparameter tuning
  --n-trials INT           Number of Optuna trials when --tune is set (default: 50)
  --output-dir PATH        Directory to save the model (default: models/)
  --practice-id TEXT       Filter training data to a specific practice GUID
  --payer-id TEXT          Filter training data to a specific payer
```

### Training Pipeline

1. **Data Fetching** — `PipelineRunner.run_full_pipeline()` fetches claims from the database, runs feature engineering, and returns a DataFrame.
2. **Data Splitting** — `prepare_training_data()` creates stratified train (70%) / validation (10%) / test (20%) splits. Supports optional time-based splitting via `--time-column`.
3. **Model Training** — `train_denial_predictor()`:
   - Creates a LightGBM or XGBoost classifier with default or Optuna-tuned hyperparameters.
   - Uses early stopping on the validation set (patience = 10 rounds).
   - Calibrates probabilities with isotonic calibration (`CalibratedClassifierCV`).
4. **Evaluation** — Computes precision, recall, F1, accuracy, specificity, sensitivity, ROC AUC, PR AUC, Brier score, and Expected Calibration Error (ECE).
5. **Serialization** — `save_model()` pickles the model, feature column list, and metadata into a `.pkl` file.

### Model File Format

The saved `.pkl` file is a dictionary:

```python
{
    "model": <CalibratedClassifierCV>,
    "feature_columns": ["total_billed_amount", "payment_ratio", ...],  # 1,788 columns
    "metadata": {
        "model_type": "lightgbm",
        "train_size": 8520,
        "val_size": 1217,
        "test_size": 2435,
        "days_back": 365,
        "metrics": {"train": {...}, "validation": {...}},
    },
}
```

### Retraining

To retrain with the latest data:

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
REPOSITORY_TYPE="database" \
python scripts/train_model.py --days-back 365 --model-type lightgbm
```

The model file at `models/denial_predictor_lightgbm.pkl` is overwritten. The API will load the new model on next startup (or restart).

### Hyperparameter Tuning

```bash
python scripts/train_model.py --days-back 365 --model-type lightgbm --tune --n-trials 100
```

Optuna explores hyperparameters like `num_leaves`, `learning_rate`, `max_depth`, `min_child_samples`, `subsample`, and `colsample_bytree`, optimizing for ROC AUC on the validation set.

---

## Running the API Server

### Start the server

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001
```

Or use the Makefile (port 8000 by default):

```bash
make serve
```

### Interactive documentation

Once running, visit:

| URL | Description |
|---|---|
| `http://localhost:8001/docs` | Swagger UI — interactive API explorer, try endpoints in-browser |
| `http://localhost:8001/redoc` | ReDoc — clean readable documentation for sharing |
| `http://localhost:8001/openapi.json` | OpenAPI 3.0 JSON schema — import into Postman, Insomnia, or code generators |

### Verify the server

```bash
curl http://localhost:8001/health
# → {"status": "ok", "version": "0.1.0"}

curl http://localhost:8001/ready
# → {"status": "ready"}
```

---

## API Endpoints Overview

All analytics and prediction endpoints are versioned under `/api/v1/`. See [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md) for full request/response schemas and examples.

### Health & Info

| Method | Path | Description |
|---|---|---|
| GET | `/` | API info with endpoint directory |
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |

### Predictions

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/predict` | Predict denial probability for a single claim |
| POST | `/api/v1/predict/batch` | Batch prediction (up to 1,000 claims) |
| GET | `/api/v1/model/info` | Model metadata, feature count, training metrics |

### Aggregate Analytics

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/analytics/practices` | All practices with denial/rejection rates, risk distribution, financials |
| GET | `/api/v1/analytics/payers` | All payers with the same metrics |
| GET | `/api/v1/analytics/practice-payer` | Practice × payer combinations |

### Practice-Specific Analytics

All endpoints below take `{practice_guid}` as a path parameter and `days_back` (default 365) as a query parameter.

| Method | Path | Description |
|---|---|---|
| GET | `.../practice/{guid}/performance-summary` | Total claims, denial rate, denied amount, recovery potential, trends, risk factors |
| GET | `.../practice/{guid}/action-items` | Prioritized recommendations sorted by financial impact |
| GET | `.../practice/{guid}/payer-performance` | Denial rates broken down by payer |
| GET | `.../practice/{guid}/cpt-performance` | Denial rates broken down by CPT code |
| GET | `.../practice/{guid}/high-risk-claims` | Individual claims with highest denial probability |
| GET | `.../practice/{guid}/denial-reasons` | CARC/RARC code frequency and financial impact |
| GET | `.../practice/{guid}/cpt-carc-correlation` | Which CPT codes get denied for which CARC/RARC reasons |
| GET | `.../practice/{guid}/rejection-patterns` | Missing/invalid field patterns causing rejections |

### System-Wide

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/analytics/overall-insights` | Cross-practice aggregation: top CARC codes, top payers, top CPTs, key findings |

---

## Generating Practice Insight Reports

The `scripts/generate_practice_insights_via_api.py` script consumes the API and generates a comprehensive Markdown report.

### Usage

```bash
# Generate for all practices
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001 &

python scripts/generate_practice_insights_via_api.py
```

```bash
# Generate for a specific practice
PRACTICE_FILTER="Performance Rehabilitation" \
python scripts/generate_practice_insights_via_api.py
```

### Output

The script writes `PRACTICE_INSIGHTS.md` containing, for each practice:
- Performance summary (total claims, denial rate, denied amount, recovery potential)
- Prioritized action items with financial impact
- Payer performance breakdown
- CPT code performance breakdown
- Top 20 high-risk claims
- CARC/RARC denial reason analysis
- CPT-CARC correlation analysis
- Rejection pattern analysis

---

## Testing

### Test Suite Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/                          # Fast, isolated, no external deps
│   ├── test_schemas.py            # Pydantic schema validation
│   ├── test_predictor.py          # Model predict/predict_batch
│   ├── test_trainer.py            # Training pipeline
│   ├── test_feature_engineering.py # Feature extraction
│   ├── test_analytics_service.py  # Service layer functions
│   ├── test_data_access.py        # Repository models
│   ├── test_code_normalization.py # Code normalization
│   └── test_denial_taxonomy.py    # Taxonomy mapping
├── api/                           # FastAPI TestClient-based
│   ├── test_app.py                # App setup, health, openapi
│   ├── test_predictions.py        # Prediction endpoints
│   └── test_analytics_routes.py   # Analytics routes
├── reports/
│   └── test_insights_report.py    # Report generation
└── integration/                   # Require live DB (marked)
    └── test_pipeline_end_to_end.py
```

### Running Tests

```bash
# All unit + API tests (excludes integration by default)
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Only unit tests
pytest tests/unit/

# Only API tests
pytest tests/api/

# Include integration tests (requires live database)
pytest -m integration

# Verbose with short tracebacks
pytest -v --tb=short
```

### Test Configuration

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short -m 'not integration'"
markers = [
    "integration: tests that require a live database or external service",
]
```

### Key Test Fixtures (conftest.py)

| Fixture | Description |
|---|---|
| `sample_claims` | List of 5 `Claim` objects with varied statuses |
| `sample_practices` | List of `Practice` objects |
| `sample_payers` | List of `Payer` objects |
| `sample_line_items` | `ClaimLineItem` objects for fixture claims |
| `sample_denial_details` | `DenialDetail` objects with CARC/RARC codes |
| `practice_predictions_df` | DataFrame simulating prediction output |
| `mock_repository` | `AsyncMock` of `ClaimsRepository` pre-configured with fixture data |
| `mock_predictor` | `MagicMock` of `DenialPredictor` returning controlled predictions |

---

## Development Workflow

### Code Style

- **Formatter**: `black` (line length 100)
- **Linter**: `ruff` (E, F, I, N, W, UP, B, C4, SIM rules)
- **Type checker**: `mypy` (warn_return_any, ignore_missing_imports)

```bash
make lint
# Or:
ruff check src tests scripts
mypy src --ignore-missing-imports
```

### Adding a New Endpoint

1. Add the Pydantic request/response schema to `src/api/schemas.py`.
2. Add the business logic function to the appropriate service in `src/services/`.
3. Add the route handler to the appropriate router in `src/api/routes/`.
4. Add tests: unit test for the service function, API test for the route.
5. Run `pytest` to verify.

### Adding a New Feature

1. Add the feature extraction logic to the appropriate module in `src/pipelines/feature_engineering/`.
2. Call the extractor from `feature_engineer_optimized.py` in the per-claim loop.
3. Register the feature in `config/feature_registry.yaml` with its type and modifiability.
4. Retrain the model to incorporate the new feature.
5. Add unit tests for the feature extractor.

### Modifying Database Queries

1. Update the relevant method in `src/data_access/db_repository.py`.
2. If the interface changes, update `src/data_access/base_repository.py` and `src/data_access/fhir_repository.py`.
3. Run integration tests to verify: `pytest -m integration`.

---

## Denial Classification Logic

A claim is classified as **denied** (`is_denied = True`) if any of these conditions hold:

1. **Full Denial** — `claim.status == ClaimStatus.DENIED` (explicit denial status from claim_status or payer_status).
2. **Denial with Details** — The claim has denial details (CARC/RARC adjustments) AND the status is not `PAID`.
3. **Significant Partial Denial** — The claim is `PAID` but the `payment_ratio` (paid / billed) is below **0.50**, indicating that more than half the billed amount was denied/adjusted. This threshold avoids counting routine fee-schedule adjustments (e.g., CARC 45) as denials when the payment was reasonable.

A claim is classified as **rejected** (`is_rejected = True`) if `claim.status == ClaimStatus.REJECTED`. Rejections are distinct from denials: they indicate the claim was not processable due to missing/invalid data, not that the service was non-covered.

### Risk Level Assignment

| Probability Range | Risk Level |
|---|---|
| 0.00 – 0.30 | Low |
| 0.30 – 0.70 | Medium |
| 0.70 – 1.00 | High |

---

## Troubleshooting

### Database Connection Issues

```bash
# Verify PostgreSQL is reachable
psql -h localhost -U tebra_user -d tebra_dw -c "SELECT 1"

# Check the connection string uses asyncpg driver
echo $DATABASE_URL
# Should start with: postgresql+asyncpg://
```

If the connection string uses `postgresql://`, the repository auto-converts it to `postgresql+asyncpg://`.

### Model Not Found (503 on /predict)

```
{"detail": "Model not found. Please train the model first."}
```

Train the model first:

```bash
python scripts/train_model.py --days-back 365 --model-type lightgbm
```

Or set `DENIAL_MODEL_PATH` to point to an existing `.pkl` file.

### Missing Features Warning

```
Missing features, filling with 0
```

This is normal when the feature matrix at prediction time has a different column set than the training data. Missing features are zero-filled. This happens when a CPT-CARC combination seen in training doesn't appear in the prediction batch.

### Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Ensure package is installed in editable mode
pip install -e ".[dev]"
```

### Ollama Not Responding

```bash
docker-compose ps          # Check container status
docker-compose restart ollama
curl http://localhost:11434/api/tags  # Test connectivity
```

### Slow Feature Engineering

The optimized pipeline should process ~12,000 claims in under 15 seconds. If it's slow:
- Check PostgreSQL connection pooling (`pool_size=10`, `max_overflow=20` in `db_repository.py`).
- Ensure the database has indexes on `claim_reference_id`, `encounter_id`, `practice_guid`, and `date_of_service`.
- Consider using `--limit` during development to work with a subset.

---

## Additional Resources

- [API Documentation](API_DOCUMENTATION.md) — Full endpoint reference with schemas and examples
- [Database Schema](docs/database_schema.md) — Auto-generated table definitions and relationships
- [Denial Taxonomy](config/denial_taxonomy.yaml) — CARC/RARC to category mapping
- [Feature Registry](config/feature_registry.yaml) — Feature definitions and modifiability
- [Practice Insights](PRACTICE_INSIGHTS.md) — Latest generated practice insight report

---

## License

Proprietary — All rights reserved.

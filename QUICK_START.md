# Quick Start Guide

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.12+
- PostgreSQL database with `tebra_dw` schema
- OpenMP library (for XGBoost/LightGBM)
  - macOS: `brew install libomp`
  - Linux: `sudo apt-get install libomp-dev`

### 2. Installation

```bash
# Clone repository
cd denial-models

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Configure Database

Create `.env` file:
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tebra_dw
```

### 4. Train Model

```bash
# Train with 365 days of data
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/tebra_dw" \
python scripts/train_model_with_env.py --days-back 365 --model-type lightgbm --tune
```

### 5. Evaluate Model

```bash
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/tebra_dw" \
python scripts/evaluate_model.py
```

### 6. Start API Server

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for interactive API documentation.

---

## 📊 Model Performance

- **Accuracy**: 98.01%
- **Recall**: 100% (0 false negatives)
- **Precision**: 92.31%
- **ROC-AUC**: 0.9992

---

## 🔧 Common Tasks

### Test Partial Payment Handling
```bash
DATABASE_URL="..." python scripts/test_partial_payments_simple.py
```

### Test SHAP Explanations
```bash
python scripts/test_shap.py
```

### Test API Locally
```bash
python scripts/test_api_local.py
```

### Make a Prediction (Python)
```python
from src.models.denial_predictor.predictor import DenialPredictor

predictor = DenialPredictor(model_path="models/denial_predictor_lightgbm.pkl")
result = predictor.predict(features=claim_features, return_explanations=True)
print(f"Denial Probability: {result['probability']:.4f}")
```

### Make a Prediction (API)
```bash
curl -X POST "http://localhost:8000/api/v1/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "test_001",
    "features": {...},
    "include_explanations": true
  }'
```

---

## 📚 Documentation

- `IMPLEMENTATION_SUMMARY.md` - Complete implementation summary
- `API_DOCUMENTATION.md` - API endpoint documentation
- `REJECTION_LOGIC.md` - Rejection vs denial handling
- `PARTIAL_PAYMENT_HANDLING.md` - Partial payment implementation
- `SHAP_RESULTS.md` - SHAP explainability results

---

## 🆘 Troubleshooting

### Model Not Found
```bash
# Train the model first
python scripts/train_model_with_env.py --days-back 365
```

### Database Connection Error
```bash
# Check DATABASE_URL in .env file
# Test connection:
python scripts/test_db_connection.py
```

### SHAP Import Error
```bash
pip install shap
```

### OpenMP Error (XGBoost/LightGBM)
```bash
# macOS
brew install libomp

# Linux
sudo apt-get install libomp-dev
```

---

## ✅ Verification Checklist

- [ ] Database connection working
- [ ] Model trained and saved
- [ ] Test set evaluation completed
- [ ] SHAP explanations working
- [ ] API server starts successfully
- [ ] API endpoints respond correctly

---

## 🎯 Next Steps

See `NEXT_STEPS.md` for:
- Code encoders (target encoding)
- Counterfactual recommendations
- Analytics & root cause analysis
- Production deployment

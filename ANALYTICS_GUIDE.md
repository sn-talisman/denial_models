# Analytics Guide - Practice & Payer Analysis

This guide explains how to use the model and API to analyze denials and rejections by practice and payer.

## 📊 Overview

The analytics system provides comprehensive analysis of denial and rejection patterns across:
- **Practices**: Identify which practices have the highest denial rates
- **Payers**: Identify which payers deny claims most frequently
- **Practice-Payer Combinations**: Find specific problem combinations

## 🚀 Usage Methods

### Method 1: Command-Line Script (Recommended for Ad-Hoc Analysis)

Run the analysis script directly:

```bash
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/tebra_dw" \
python scripts/analyze_practice_payer.py
```

**Output:**
- Console output with top practices, payers, and combinations
- CSV files saved to `analysis_results/`:
  - `practice_analysis.csv` - Practice-level metrics
  - `payer_analysis.csv` - Payer-level metrics
  - `practice_payer_analysis.csv` - Combination metrics
  - `all_predictions_with_analysis.csv` - Full dataset with predictions

**Example Output:**
```
📊 Analysis by Practice
📈 Top 10 Practices by Denial Rate:
Practice Name                            Claims   Denied   Rate     Avg Prob   High Risk 
Unknown                                  160      107      66.9%    0.650      67.5%     

📊 Analysis by Payer
📈 Top 10 Payers by Denial Rate:
Payer Name                               Claims   Denied   Rate     Avg Prob   High Risk 
Medicare of Nevada                       1        1        100.0%   0.718      100.0%    

📊 Summary Statistics
Overall:
   Total Claims: 1,000
   Denied: 240 (24.0%)
   Average Denial Probability: 0.2397
   High Risk Claims: 223 (22.3%)
```

### Method 2: REST API Endpoints

Start the API server:
```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

#### 1. Analyze by Practice

```bash
curl "http://localhost:8000/api/v1/analytics/practices?days_back=365&min_claims=5"
```

**Response:**
```json
[
  {
    "practice_id": "practice_123",
    "practice_name": "Family Practice",
    "total_claims": 160,
    "denied_claims": 107,
    "rejected_claims": 0,
    "denied_or_rejected": 107,
    "denial_rate": 0.66875,
    "rejection_rate": 0.0,
    "denial_or_rejection_rate": 0.66875,
    "avg_denial_probability": 0.65,
    "high_risk_count": 108,
    "medium_risk_count": 20,
    "low_risk_count": 32,
    "high_risk_pct": 0.675,
    "total_billed": 50000.0,
    "denied_billed": 30000.0,
    "denied_billed_pct": 0.6
  }
]
```

#### 2. Analyze by Payer

```bash
curl "http://localhost:8000/api/v1/analytics/payers?days_back=365&min_claims=5"
```

**Response:**
```json
[
  {
    "payer_id": "payer_456",
    "payer_name": "Medicare of Nevada",
    "total_claims": 50,
    "denied_claims": 25,
    "denial_rate": 0.5,
    "avg_denial_probability": 0.55,
    "high_risk_count": 20,
    "total_billed": 15000.0,
    "denied_billed": 7500.0
  }
]
```

#### 3. Analyze Practice-Payer Combinations

```bash
curl "http://localhost:8000/api/v1/analytics/practice-payer?days_back=365&min_claims=5"
```

**Response:**
```json
[
  {
    "practice_id": "practice_123",
    "practice_name": "Family Practice",
    "payer_id": "payer_456",
    "payer_name": "Medicare of Nevada",
    "total_claims": 20,
    "denied_claims": 15,
    "denial_rate": 0.75,
    "avg_denial_probability": 0.8,
    "high_risk_count": 18
  }
]
```

### Method 3: Python Programmatic Access

```python
import asyncio
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer import engineer_features_batch
from src.models.denial_predictor.predictor import DenialPredictor
from datetime import date, timedelta

async def analyze_practices():
    repository = get_repository()
    predictor = DenialPredictor(model_path="models/denial_predictor_lightgbm.pkl")
    
    # Fetch claims
    date_to = date.today()
    date_from = date_to - timedelta(days=365)
    claims = await repository.get_claims(date_from=date_from, date_to=date_to)
    
    # Engineer features
    df = await engineer_features_batch(claims, repository, date_to)
    
    # Make predictions
    exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                   'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                   'cpt_code', 'cpt_category', 'is_denied']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    features_df = df[feature_cols].fillna(0)
    
    # Convert object columns to numeric
    for col in features_df.columns:
        if features_df[col].dtype == 'object':
            features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
    features_df = features_df.fillna(0)
    
    predictions_df = predictor.predict_batch(features_df)
    
    # Add practice/payer IDs
    claim_to_practice = {c.claim_id: c.practice_id for c in claims}
    claim_to_payer = {c.claim_id: c.payer_id for c in claims}
    predictions_df['practice_id'] = predictions_df['claim_id'].map(claim_to_practice)
    predictions_df['payer_id'] = predictions_df['claim_id'].map(claim_to_payer)
    
    # Analyze by practice
    for practice_id in predictions_df['practice_id'].dropna().unique():
        practice_data = predictions_df[predictions_df['practice_id'] == practice_id]
        denial_rate = practice_data['is_denied'].mean()
        avg_prob = practice_data['denial_probability'].mean()
        print(f"Practice {practice_id}: {denial_rate:.1%} denial rate, {avg_prob:.3f} avg probability")
    
    await repository.close()

asyncio.run(analyze_practices())
```

## 📈 Metrics Explained

### Practice/Payer Metrics

- **total_claims**: Total number of claims in the period
- **denied_claims**: Number of claims that were denied
- **rejected_claims**: Number of claims currently in rejected state
- **denial_rate**: Percentage of claims denied (denied_claims / total_claims)
- **rejection_rate**: Percentage of claims rejected (rejected_claims / total_claims)
- **avg_denial_probability**: Average model-predicted denial probability
- **high_risk_count**: Number of claims predicted as high risk (>70% probability)
- **high_risk_pct**: Percentage of claims predicted as high risk
- **total_billed**: Total dollar amount billed
- **denied_billed**: Total dollar amount denied
- **denied_billed_pct**: Percentage of billed amount denied

### Model Predictions

The analysis uses the trained ML model to:
- **Predict denial probability** for each claim
- **Categorize risk levels**:
  - Low: <30% probability
  - Medium: 30-70% probability
  - High: >70% probability
- **Compare predictions to actual outcomes** to identify patterns

## 🎯 Use Cases

### 1. Identify Problem Practices

Find practices with high denial rates:
```python
# Practices with >50% denial rate
high_denial_practices = practice_df[practice_df['denial_rate'] > 0.5]
```

### 2. Identify Problem Payers

Find payers that deny frequently:
```python
# Payers with >40% denial rate
problem_payers = payer_df[payer_df['denial_rate'] > 0.4]
```

### 3. Find Practice-Payer Problem Combinations

Identify specific combinations that need attention:
```python
# Combinations with >60% denial rate
problem_combos = combo_df[combo_df['denial_rate'] > 0.6]
```

### 4. Financial Impact Analysis

Calculate revenue at risk:
```python
# Practices with >$10k in denied claims
high_impact = practice_df[practice_df['denied_billed'] > 10000]
```

### 5. Model Validation

Compare model predictions to actual outcomes:
```python
# Practices where model predicts high risk but actual denial rate is low
false_positives = practice_df[
    (practice_df['high_risk_pct'] > 0.5) & 
    (practice_df['denial_rate'] < 0.2)
]
```

## 📊 Interpreting Results

### High Denial Rate + High Model Probability
- **Action**: Immediate attention required
- **Likely Cause**: Systematic issues (billing errors, documentation problems)
- **Recommendation**: Review claim submission process, provide training

### High Denial Rate + Low Model Probability
- **Action**: Investigate unexpected denials
- **Likely Cause**: New denial patterns not captured in training data
- **Recommendation**: Review denial reasons, update model if needed

### Low Denial Rate + High Model Probability
- **Action**: Preventive measures
- **Likely Cause**: Model identifies at-risk claims before denial
- **Recommendation**: Proactive review of high-risk claims before submission

### Low Denial Rate + Low Model Probability
- **Action**: Maintain current practices
- **Likely Cause**: Good claim quality and payer relationships
- **Recommendation**: Continue current processes, share best practices

## 🔧 Customization

### Adjust Time Window

```bash
# Analyze last 90 days
curl "http://localhost:8000/api/v1/analytics/practices?days_back=90"
```

### Filter by Minimum Claims

```bash
# Only include practices with at least 20 claims
curl "http://localhost:8000/api/v1/analytics/practices?min_claims=20"
```

### Export to CSV

The script automatically saves results to CSV. For API results:

```python
import requests
import pandas as pd

response = requests.get("http://localhost:8000/api/v1/analytics/practices")
data = response.json()
df = pd.DataFrame(data)
df.to_csv("practice_analysis.csv", index=False)
```

## 📝 Notes

- **Practice Names**: May show as "Unknown" if practice_id mapping is incomplete
- **Data Freshness**: Results reflect data as of the last claim fetch
- **Model Accuracy**: Predictions are based on the trained model; actual outcomes may vary
- **Rejections**: Only counts claims still in rejected state (not fixed/re-submitted)

## 🚀 Next Steps

1. **Schedule Regular Analysis**: Run weekly/monthly to track trends
2. **Set Up Alerts**: Monitor for sudden increases in denial rates
3. **Root Cause Analysis**: Use SHAP explanations to understand why specific practices/payers have high denial rates
4. **Action Plans**: Create targeted improvement plans for high-denial practices/payers


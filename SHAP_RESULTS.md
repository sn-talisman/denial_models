# SHAP Explainability Results

## ✅ Implementation Complete

SHAP explainability has been successfully implemented and tested!

## Key Findings

### Top Contributing Features

From the batch explanation across 10 test claims:

1. **`has_partial_denial`** (0.0923) - Most important feature
   - Indicates if claim has partial denial with CARC/RARC codes
   - Strong predictor of denial risk

2. **`adjustment_ratio`** (0.0134) - Adjustment amount ratio
   - Ratio of adjustments to billed amount
   - Higher ratio = higher denial risk

3. **`days_since_service`** (0.0083) - Time since service date
   - Older claims may have different denial patterns

4. **`hist_total_claims_practice`** (0.0072) - Practice-level historical claims
   - Practice volume indicator

5. **`total_paid_amount`** (0.0072) - Total paid amount
   - Lower paid amounts associated with denials

## Example Explanations

### High Risk Claim (94.12% denial probability)

**Top Features Pushing Towards DENIAL:**
- `has_partial_denial`: +0.1092 (strongest indicator)
- `adjustment_ratio`: +0.0244
- `payment_ratio`: +0.0114

**Top Features Pushing Towards APPROVAL:**
- `days_since_service`: -0.0214
- `total_paid_amount`: -0.0086

### Low Risk Claim (0% denial probability)

**Top Features Pushing Towards APPROVAL:**
- `has_partial_denial`: -0.0756 (not present = lower risk)
- `days_since_service`: -0.0043
- `month_sin`: -0.0028

## Integration

✅ SHAP explainer integrated into `DenialPredictor` class
✅ Automatic fallback to model feature importance if SHAP unavailable
✅ Works with CalibratedClassifierCV wrapper
✅ Supports both individual and batch explanations

## Usage

### In Predictor Class

```python
from src.models.denial_predictor.predictor import DenialPredictor

predictor = DenialPredictor(model_path="models/denial_predictor_lightgbm.pkl")

# Get prediction with SHAP explanations
result = predictor.predict(
    features=claim_features,
    return_explanations=True
)

# Access feature importance
top_features = list(result['feature_importance'].items())[:10]
```

### Direct SHAP Usage

```python
from src.models.explainability.shap_explainer import SHAPExplainer

explainer = SHAPExplainer(model, feature_columns, model_type="lightgbm")

# Explain single prediction
explanation = explainer.explain_prediction(features)

# Explain batch
batch_explanation = explainer.explain_batch(features_df)
```

## Insights

1. **Partial Denials are Key**: The `has_partial_denial` feature is the strongest predictor, confirming the importance of our partial payment handling implementation.

2. **Adjustment Patterns Matter**: `adjustment_ratio` is a strong indicator - claims with higher adjustment ratios are more likely to be denied.

3. **Payment History**: Lower paid amounts and payment ratios are associated with denials.

4. **Temporal Patterns**: `days_since_service` shows different patterns for denied vs approved claims.

## Next Steps

- [ ] Add SHAP visualizations (waterfall plots, summary plots)
- [ ] Create interactive explanation dashboard
- [ ] Add SHAP to API responses
- [ ] Generate explanation reports for high-risk claims


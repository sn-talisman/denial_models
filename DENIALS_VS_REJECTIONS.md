# Denials vs Rejections: Current Implementation & Recommendations

## Current Implementation

### Status Mapping (`db_repository.py`)
- **DENIED**: Status contains "denied" or "denial" → `ClaimStatus.DENIED`
- **REJECTED**: Status contains "rejected" or "reject" → `ClaimStatus.REJECTED`
- Both are separate enum values

### Feature Engineering (`claim_features.py`)
- **Current**: `is_denied = True` if status is `DENIED` OR `REJECTED`
- **Also checks**: Denial details (adjustments_json/adjustment_descriptions) to catch denials not reflected in status

### Healthcare Billing Distinction

**Rejections:**
- Happen **before** claim is accepted by payer
- Technical/administrative issues:
  - Formatting errors
  - Missing required fields
  - Invalid codes
  - Claim not accepted into payer system
- Usually fixable by correcting claim format/data

**Denials:**
- Happen **after** claim is accepted and adjudicated
- Clinical/business logic issues:
  - Medical necessity
  - Coverage issues
  - Prior authorization
  - Contractual adjustments
- Require clinical documentation or appeals

## Current Approach: Combined

We're currently treating both as `is_denied = True` because:
1. **Both represent "not paid" outcomes** - the primary prediction target
2. **Similar prevention strategies** - both indicate issues that need fixing
3. **Simpler model** - one binary classification problem

## Potential Improvements

### Option 1: Add Separate Features (Recommended)
Keep combined target but add granular features:

```python
features["is_denied"] = (status == DENIED or status == REJECTED)  # Combined target
features["is_rejected"] = (status == REJECTED)  # Additional feature
features["is_denied_clinical"] = (status == DENIED)  # Additional feature
```

**Benefits:**
- Model can learn different patterns for rejections vs denials
- Still predicts overall "not paid" outcome
- Provides more interpretable features

### Option 2: Separate Models
Train two models:
- `rejection_predictor`: Predicts technical/administrative rejections
- `denial_predictor`: Predicts clinical/business logic denials

**Benefits:**
- More targeted predictions
- Different feature sets for each
- Better root cause analysis

**Drawbacks:**
- More complex
- Need to decide which model to use for each claim

### Option 3: Multi-class Target
Change from binary to multi-class:
- `paid` (0)
- `rejected` (1) 
- `denied` (2)

**Benefits:**
- Captures full outcome space
- Can predict specific outcome type

**Drawbacks:**
- More complex model
- May need more data per class

## Recommendation

**For now: Keep combined approach** (`is_denied = denied OR rejected`) because:
1. Both represent "not paid" - the primary business outcome
2. Similar prevention value - both need to be fixed
3. Simpler model is easier to deploy and interpret

**Future enhancement: Add granular features** like `is_rejected` and `is_denied_clinical` as additional features (not separate targets) so the model can learn different patterns while still predicting the combined outcome.

## Data Quality Check Needed

We should verify:
1. Are rejections and denials actually distinct in the data?
2. Do they have different CARC code patterns?
3. Do they have different root causes?
4. Should we model them separately?

Run `scripts/analyze_denials_vs_rejections.py` to investigate the actual data distribution.


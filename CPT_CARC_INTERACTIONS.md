# CPT-CARC/RARC Interaction Features & Rejection Patterns

## Overview

The ML model now includes **interaction features** that capture the relationship between:
1. **Procedure codes (CPT) and denial reason codes (CARC/RARC)** - for DENIALS
2. **Procedure codes (CPT) and claim content issues** - for REJECTIONS

This is critical for the model to learn which procedure codes are associated with which outcomes.

## Key Distinction: Denials vs Rejections

### Denials (Post-Payer)
- Happen **AFTER** claim is sent to payer
- Payer adjudicates and provides **CARC/RARC codes** explaining the denial
- Use `cpt_carc_interactions.py` to link CPT codes to CARC/RARC codes

### Rejections (Pre-Payer)
- Happen **BEFORE** claim reaches payer
- Caused by **missing or incorrect fields** in the claim itself
- **No CARC/RARC codes** (payer never saw the claim)
- Use `rejection_patterns.py` to link CPT codes to claim content issues

## Problem Statement

Previously, the model only had:
- Separate CPT code features
- Separate CARC/RARC count features
- **No relationship** between what's submitted (CPT codes) and the outcome (denial reasons)

This meant the model couldn't learn patterns like:
- "CPT 97110 is often denied with CARC 45 (fee schedule)"
- "CPT 97112 is often denied with CARC 50 (medical necessity)"

## Solution

### New Feature Engineering Module

Created `src/pipelines/feature_engineering/cpt_carc_interactions.py` which:

1. **Matches denial details to line items**: Links CARC/RARC codes to specific CPT codes via `line_item_id`

2. **Creates interaction features**:
   - `has_cpt_{cpt_code}_carc_{carc_code}`: Binary features for common CPT-CARC combinations
   - `primary_cpt_carc_count`: Number of unique CARC codes for primary CPT
   - `primary_cpt_rarc_count`: Number of unique RARC codes for primary CPT
   - `primary_cpt_most_common_carc`: Most frequent CARC code for primary CPT
   - `primary_cpt_has_carc`: Binary indicator if primary CPT has any CARC codes
   - `primary_cpt_has_rarc`: Binary indicator if primary CPT has any RARC codes

3. **Tracks combinations**: Counts how many times each CPT-CARC/RARC combination appears

### Integration

The interaction features are now automatically included in the feature engineering pipeline:

```python
# In feature_engineer_optimized.py
from src.pipelines.feature_engineering.cpt_carc_interactions import (
    extract_cpt_carc_interaction_features,
)

interaction_features = extract_cpt_carc_interaction_features(
    claim=claim,
    line_items=line_items,
    denial_details=denial_details,
    primary_cpt=primary_cpt,
)
claim_features.update(interaction_features)
```

## Features Created

### For Training Data

When we have denial details (actual outcomes), we create:
- **Binary features**: `has_cpt_97110_carc_45 = 1` if that combination occurred
- **Count features**: How many CARC codes are associated with the primary CPT
- **Most common CARC**: The most frequent denial reason for this CPT

### For Prediction

During prediction, the model uses:
- The learned relationships from training
- Historical CPT-payer denial rates (existing features)
- The interaction features help the model apply learned patterns

## Example

For a claim with:
- Primary CPT: `97110`
- Denial detail: CARC `45` (fee schedule)

The model will see:
- `has_cpt_97110_carc_45 = 1`
- `primary_cpt_carc_count = 1`
- `primary_cpt_most_common_carc = 45`
- `primary_cpt_has_carc = 1`

This allows the model to learn: "When CPT 97110 is submitted, it's often denied with CARC 45"

## Impact

1. **Better predictions**: Model can now learn procedure-specific denial patterns
2. **Actionable insights**: Can identify which CPT codes are problematic with which denial reasons
3. **Root cause analysis**: Understands the relationship between what's submitted and why it's denied

## Next Steps

1. **Historical CPT-CARC rates**: Add historical features like `hist_denial_rate_cpt_97110_carc_45` for prediction
2. **Feature importance**: Analyze which CPT-CARC combinations are most predictive
3. **Model retraining**: Retrain the model with these new features to improve accuracy

## Rejection Pattern Features

### Module: `rejection_patterns.py`

Creates features that identify potential rejection causes:

1. **Missing Required Fields**:
   - `missing_patient_id`: Patient ID not provided
   - `missing_provider_id`: Provider ID not provided
   - `missing_claim_number`: Claim number missing
   - `missing_service_date`: Service date missing
   - `missing_submitted_date`: Submitted date missing

2. **Invalid Data Patterns**:
   - `invalid_date_order`: Submitted date before service date
   - `invalid_cpt_count`: Number of invalid CPT codes
   - `missing_cpt_in_line_items`: Line items without CPT codes
   - `missing_billed_amount`: No billed amount

3. **CPT-Specific Rejection Features**:
   - `cpt_{cpt_code}_missing_patient_id`: This CPT often rejected due to missing patient ID
   - `cpt_{cpt_code}_missing_provider_id`: This CPT often rejected due to missing provider ID
   - `cpt_{cpt_code}_invalid_date_order`: This CPT often rejected due to date issues
   - `cpt_{cpt_code}_rejection_risk_score`: Overall rejection risk for this CPT
   - `cpt_{cpt_code}_has_rejection_risk`: Binary indicator of rejection risk

4. **Claim Completeness**:
   - `claim_completeness_score`: 0-10 score of claim completeness
   - `is_incomplete_claim`: Binary indicator if claim is incomplete

## Example

For a rejected claim with:
- Primary CPT: `97110`
- Missing patient ID
- Invalid date order

The model will see:
- `cpt_97110_missing_patient_id = 1`
- `cpt_97110_invalid_date_order = 1`
- `cpt_97110_rejection_risk_score = 5`
- `cpt_97110_has_rejection_risk = 1`

This allows the model to learn: "When CPT 97110 is submitted with missing patient ID, it gets rejected"

## Files Modified

- `src/pipelines/feature_engineering/cpt_carc_interactions.py` (NEW) - For denials with CARC/RARC codes
- `src/pipelines/feature_engineering/rejection_patterns.py` (NEW) - For rejections based on claim content
- `src/pipelines/feature_engineering/feature_engineer_optimized.py` (UPDATED) - Integrates both


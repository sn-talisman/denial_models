# Partial Payment Handling

## Overview

Partially paid claims are an important category where:
- The claim **was paid** (status = PAID)
- But **not the full amount** (payment_ratio < 1.0)
- Insurance provides **CARC/RARC codes** explaining why certain amounts weren't paid

These are valuable for training because we have the **adjustment reasons** (CARC/RARC codes) that explain the partial denial.

## Feature Engineering

### Payment Features

```python
# Basic payment metrics
total_billed_amount: float
total_paid_amount: float
payment_ratio: float  # paid / billed

# Partial payment detection
is_partially_paid: bool  # paid > 0 AND payment_ratio < 1.0
adjustment_amount: float  # billed - paid
adjustment_ratio: float  # adjustment / billed
```

### Adjustment Features

```python
# Denial detail features (from CARC/RARC codes)
denial_detail_count: int  # Number of adjustment records
has_adjustments: bool  # denial_detail_count > 0
unique_carc_count: int  # Number of unique CARC codes
unique_rarc_count: int  # Number of unique RARC codes
total_adjustment_from_details: float  # Sum of adjustment amounts
has_partial_denial: bool  # Partially paid with adjustments
```

## Data Flow

1. **Claim Status Check**:
   - If `status = PAID` and `payment_ratio < 1.0` → Partially paid
   - If `status = PAID` and `payment_ratio >= 1.0` → Fully paid (ignore previous rejections)
   - If `status = DENIED` → Fully denied

2. **Denial Details Extraction**:
   - Always fetch denial details (includes adjustments for paid claims)
   - Extract CARC/RARC codes from `adjustments_json` and `adjustment_descriptions`
   - Calculate `adjustment_amount = billed_amount - paid_amount` for each line item

3. **Feature Assignment**:
   - **Fully paid**: `has_partial_denial = False`, ignore adjustments
   - **Partially paid**: `has_partial_denial = True`, capture CARC/RARC codes
   - **Fully denied**: `is_denied = True`, capture all denial details

## Example Scenarios

### Scenario 1: Fully Paid Claim
```
Status: PAID
Billed: $100
Paid: $100
Payment Ratio: 1.0
Adjustments: None

Result:
- is_denied = False
- is_partially_paid = False
- has_partial_denial = False
- Ignore any previous rejection history
```

### Scenario 2: Partially Paid Claim
```
Status: PAID
Billed: $100
Paid: $70
Payment Ratio: 0.7
Adjustments: CARC-45 (Contractual Obligation), RARC-M1

Result:
- is_denied = False (claim was paid)
- is_partially_paid = True
- has_partial_denial = True
- adjustment_amount = $30
- adjustment_ratio = 0.3
- unique_carc_count = 1
- unique_rarc_count = 1
- Capture CARC/RARC codes for training
```

### Scenario 3: Fully Denied Claim
```
Status: DENIED
Billed: $100
Paid: $0
Payment Ratio: 0.0
Adjustments: CARC-96 (Non-covered charge)

Result:
- is_denied = True
- is_partially_paid = False
- has_partial_denial = False (not partial, it's full)
- Capture all denial details
```

## Database Query Updates

The `get_denial_details` query now includes:
```sql
SELECT 
    ...,
    billed_amount,
    paid_amount,
    (billed_amount - COALESCE(paid_amount, 0)) as adjustment_amount
FROM tebra.fin_claim_line
```

This allows us to:
- Calculate adjustment amounts per line item
- Include adjustment amounts in `DenialDetail` objects
- Aggregate adjustment amounts for feature engineering

## Model Training Implications

### Target Variable
- **Primary target**: `is_denied` (full denials only)
- **Secondary features**: `has_partial_denial`, `adjustment_ratio` (for partial denials)

### Training Data
- **Full denials**: Use as positive examples (`is_denied = True`)
- **Partial denials**: Use as features but not as "denied" target
- **Fully paid**: Use as negative examples (`is_denied = False`)

### Model Capabilities
The model can learn:
1. **Full denial prediction**: Will this claim be fully denied?
2. **Partial denial patterns**: Which CARC/RARC codes lead to adjustments?
3. **Adjustment amount prediction**: How much will be adjusted?

## Benefits

1. **Richer training data**: Partially paid claims provide known adjustment reasons
2. **Better predictions**: Model learns patterns from both full and partial denials
3. **Actionable insights**: CARC/RARC codes tell us exactly why adjustments occurred
4. **Revenue optimization**: Predict and prevent partial denials before submission


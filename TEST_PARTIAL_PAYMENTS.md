# Testing Partial Payment Handling

## What Was Implemented

### 1. Partial Payment Detection (`claim_features.py`)
- `is_partially_paid`: True if `paid_amount > 0` AND `payment_ratio < 1.0`
- `adjustment_amount`: `billed_amount - paid_amount`
- `adjustment_ratio`: `adjustment_amount / billed_amount`

### 2. Adjustment Feature Extraction (`feature_engineer.py`)
- Extracts CARC/RARC codes from denial details for partially paid claims
- Features added:
  - `denial_detail_count`: Number of adjustment records
  - `has_adjustments`: Whether adjustments exist
  - `unique_carc_count`: Number of unique CARC codes
  - `unique_rarc_count`: Number of unique RARC codes
  - `total_adjustment_from_details`: Sum of adjustment amounts
  - `has_partial_denial`: Partially paid with adjustments

### 3. Database Query Updates (`db_repository.py`)
- `get_denial_details` now includes `billed_amount`, `paid_amount`, and calculated `adjustment_amount`
- Extracts adjustment amounts from JSON and calculates from `billed - paid`
- Includes adjustment amounts in `DenialDetail` objects

## How to Test

### Option 1: Run the Test Script

```bash
# Activate virtual environment
source venv/bin/activate

# Set database URL
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"

# Run test
python scripts/test_partial_payments_simple.py
```

### Option 2: Run Full Training Pipeline

```bash
# Activate virtual environment
source venv/bin/activate

# Set database URL
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"

# Run training with 90 days of data (smaller test)
python scripts/train_model_with_env.py --days-back 90 --limit 100 --model-type lightgbm
```

## Expected Output

The test should show:

1. **Payment Status Analysis**
   - Payment ratio statistics (mean, min, max, median)
   - Counts of fully paid, partially paid, and not paid claims

2. **Partial Payment Features**
   - Presence of all new features
   - Statistics for each feature (mean, max, counts)

3. **Example Claims**
   - Sample partially paid claims with:
     - Payment ratio
     - Adjustment amount
     - CARC/RARC code counts
     - Denial detail counts

## What to Verify

### ✅ Feature Presence
- All 9 partial payment features should be present:
  - `is_partially_paid`
  - `adjustment_amount`
  - `adjustment_ratio`
  - `has_partial_denial`
  - `denial_detail_count`
  - `has_adjustments`
  - `unique_carc_count`
  - `unique_rarc_count`
  - `total_adjustment_from_details`

### ✅ Logic Correctness
- **Fully paid claims** (payment_ratio >= 1.0): Should have `is_partially_paid = False`
- **Partially paid claims** (0 < payment_ratio < 1.0): Should have `is_partially_paid = True`
- **Not paid claims** (payment_ratio = 0): Should have `is_partially_paid = False`

### ✅ CARC/RARC Extraction
- Claims with adjustments should have `denial_detail_count > 0`
- Claims with CARC codes should have `unique_carc_count > 0`
- Claims with RARC codes should have `unique_rarc_count > 0`

### ✅ Adjustment Amounts
- `adjustment_amount` should equal `billed_amount - paid_amount`
- `adjustment_ratio` should equal `adjustment_amount / billed_amount`
- `total_adjustment_from_details` should sum adjustment amounts from denial details

## Troubleshooting

### If features are missing:
1. Check that `feature_engineer.py` is calling `get_denial_details`
2. Verify that `claim_features.py` calculates `is_partially_paid` correctly
3. Ensure database query includes `adjustment_amount` calculation

### If no partially paid claims found:
1. Check if your data actually has partially paid claims
2. Verify `payment_ratio` calculation: `paid_amount / billed_amount`
3. Check that `paid_amount > 0` and `billed_amount > paid_amount`

### If CARC/RARC codes not extracted:
1. Verify `adjustments_json` or `adjustment_descriptions` exist in database
2. Check that `get_denial_details` is parsing JSON correctly
3. Ensure regex pattern matches your CARC code format

## Next Steps After Testing

Once testing confirms everything works:

1. **Run full training** with 365 days of data
2. **Verify model training** includes partial payment features
3. **Check feature importance** to see if partial payment features are predictive
4. **Validate predictions** on test set


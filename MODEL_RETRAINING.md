# Model Retraining with New Features

## New Features Added

The model now includes **interaction features** that capture relationships between:

1. **CPT Codes and CARC/RARC Codes** (for DENIALS)
   - Features like `has_cpt_97110_carc_45` 
   - Links procedure codes to payer denial reasons
   - ~14 features per common CARC code

2. **CPT Codes and Rejection Patterns** (for REJECTIONS)
   - Features like `cpt_97110_missing_patient_id`
   - Links procedure codes to claim content issues
   - Captures missing fields, invalid data, date issues

**Total new features: ~53 interaction features**

## How to Retrain

### Option 1: Using the Script

```bash
./RETRAIN_MODEL.sh
```

### Option 2: Manual Command

```bash
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"
python3 scripts/train_model_with_env.py \
    --days-back 365 \
    --model-type lightgbm \
    --tune \
    --n-trials 50
```

### Option 3: Quick Test (Smaller Dataset)

For faster testing with a smaller dataset:

```bash
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"
python3 scripts/train_model_with_env.py \
    --days-back 180 \
    --model-type lightgbm \
    --tune \
    --n-trials 20 \
    --limit 5000
```

## Expected Output

The training will:
1. Fetch claims from the database (12K+ claims for 365 days)
2. Engineer features including the new interaction features
3. Split into train/validation/test sets
4. Run hyperparameter tuning (50 trials)
5. Train the final model
6. Save to `models/denial_predictor_lightgbm.pkl`

## Training Time

- **Full training** (365 days, 50 trials): ~20-30 minutes
- **Quick test** (180 days, 20 trials, 5K claims): ~5-10 minutes

## What the Model Will Learn

After retraining, the model will understand:

1. **Denial Patterns**: 
   - "CPT 97110 is often denied with CARC 45 (fee schedule)"
   - "CPT 97112 is often denied with CARC 50 (medical necessity)"

2. **Rejection Patterns**:
   - "CPT 99214 with missing patient ID gets rejected"
   - "CPT 97110 with invalid date order gets rejected"

3. **Combined Predictions**:
   - Can predict both denial risk (based on CARC patterns) and rejection risk (based on claim content)

## Verification

After training, verify the new features are being used:

```python
import pickle
with open('models/denial_predictor_lightgbm.pkl', 'rb') as f:
    model_data = pickle.load(f)
    
features = model_data['feature_columns']
interaction_features = [f for f in features if 'cpt_' in f.lower() and ('carc' in f.lower() or 'rejection' in f.lower())]
print(f"New interaction features: {len(interaction_features)}")
```

## Next Steps

1. **Evaluate the model**: Compare metrics before/after
2. **Feature importance**: Check which interaction features are most predictive
3. **Update API**: The predictor will automatically use the new model
4. **Monitor**: Track if predictions improve in production


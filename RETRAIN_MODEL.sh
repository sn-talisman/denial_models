#!/bin/bash
# Script to retrain the model with new CPT-CARC/RARC interaction features

echo "🚀 Starting model retraining with new features..."
echo "   - CPT-CARC/RARC interaction features (for denials)"
echo "   - Rejection pattern features (for rejections)"
echo ""

# Set database URL
export DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw"

# Activate virtual environment (if needed)
# source venv/bin/activate

# Run training with hyperparameter tuning
python3 scripts/train_model_with_env.py \
    --days-back 365 \
    --model-type lightgbm \
    --tune \
    --n-trials 50

echo ""
echo "✅ Training complete! Model saved to models/denial_predictor_lightgbm.pkl"


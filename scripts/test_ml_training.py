#!/usr/bin/env python3
"""Quick test of ML training pipeline with synthetic data."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.denial_predictor.trainer import (
    prepare_training_data,
    train_denial_predictor,
    save_model,
)
from src.models.denial_predictor.predictor import DenialPredictor
from src.utils.metrics import calculate_denial_metrics

# Create synthetic training data
print("📊 Creating synthetic training data...")
np.random.seed(42)
n_samples = 200
n_features = 20

# Generate features
X = pd.DataFrame(
    np.random.randn(n_samples, n_features),
    columns=[f"feature_{i}" for i in range(n_features)]
)

# Generate target with some correlation to features
y = (X.iloc[:, 0] + X.iloc[:, 1] - X.iloc[:, 2] + np.random.randn(n_samples) > 0).astype(int)

# Create DataFrame with target
df = X.copy()
df["is_denied"] = y
df["claim_id"] = range(len(df))

print(f"   Created {len(df)} samples")
print(f"   Features: {len(X.columns)}")
print(f"   Denied: {y.sum()} ({y.mean():.1%})")

# Prepare training data
print("\n📦 Preparing train/validation/test splits...")
X_train, X_val, y_train, y_val, X_test, y_test = prepare_training_data(
    df,
    target_column="is_denied",
    test_size=0.2,
    validation_size=0.1,
    random_state=42,
)

print(f"   Train: {len(X_train)}")
print(f"   Validation: {len(X_val)}")
print(f"   Test: {len(X_test)}")

# Train model
print("\n🤖 Training LightGBM model...")
model, metrics = train_denial_predictor(
    X_train=X_train,
    y_train=y_train,
    X_val=X_val,
    y_val=y_val,
    model_type="lightgbm",
    use_hyperparameter_tuning=False,  # Quick test
    calibrate=True,
)

print("\n✅ Model Training Complete!")
print(f"\n📈 Training Metrics:")
for key, value in metrics["train"].items():
    if isinstance(value, (int, float)) and key not in ["true_positives", "true_negatives", "false_positives", "false_negatives"]:
        print(f"   {key}: {value:.4f}")

if "validation" in metrics:
    print(f"\n📈 Validation Metrics:")
    for key, value in metrics["validation"].items():
        if isinstance(value, (int, float)) and key not in ["true_positives", "true_negatives", "false_positives", "false_negatives"]:
            print(f"   {key}: {value:.4f}")

# Test prediction
print("\n🔮 Testing predictions...")
predictor = DenialPredictor(model=model)
predictor.feature_columns = list(X_train.columns)

# Single prediction
sample_features = X_test.iloc[0].to_dict()
prediction = predictor.predict(sample_features)
print(f"\n   Single Prediction:")
print(f"      Probability: {prediction['probability']:.4f}")
print(f"      Risk Level: {prediction['risk_level']}")
print(f"      Prediction: {'DENIED' if prediction['prediction'] == 1 else 'PAID'}")

# Batch prediction
batch_predictions = predictor.predict_batch(X_test.head(10))
print(f"\n   Batch Predictions (10 samples):")
print(f"      Average probability: {batch_predictions['denial_probability'].mean():.4f}")
print(f"      Risk distribution:")
for risk, count in batch_predictions['risk_level'].value_counts().items():
    print(f"         {risk}: {count}")

# Test model save/load
print("\n💾 Testing model persistence...")
from src.models.denial_predictor.trainer import save_model, load_model
from pathlib import Path

model_path = Path("models/test_model.pkl")
save_model(
    model=model,
    model_path=model_path,
    feature_columns=list(X_train.columns),
    metadata={"test": True},
)

loaded_model, loaded_features, loaded_metadata = load_model(model_path)
print(f"   ✅ Model saved and loaded successfully")
print(f"   Features: {len(loaded_features)}")
print(f"   Metadata: {loaded_metadata}")

# Test loaded model
loaded_predictor = DenialPredictor(model=loaded_model)
loaded_predictor.feature_columns = loaded_features
test_pred = loaded_predictor.predict(sample_features)
print(f"   ✅ Loaded model prediction: {test_pred['probability']:.4f}")

print("\n🎉 All tests passed! ML training pipeline is working correctly.")


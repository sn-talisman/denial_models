#!/usr/bin/env python3
"""Test API endpoints locally without starting server.

Tests the API logic directly by importing and calling the functions.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.routes.predictions import get_predictor
from src.api.schemas import PredictionRequest, BatchPredictionRequest
from src.models.denial_predictor.predictor import DenialPredictor


def test_api_locally():
    """Test API endpoints locally."""
    print("=" * 60)
    print("Testing API Endpoints (Local)")
    print("=" * 60)
    
    # Test predictor loading
    print("\n1. Testing Predictor Loading...")
    try:
        predictor = get_predictor()
        print(f"✅ Predictor loaded")
        print(f"   Model Type: {predictor.model_type}")
        print(f"   Features: {len(predictor.feature_columns)}")
    except Exception as e:
        print(f"❌ Failed to load predictor: {e}")
        return
    
    # Test model info
    print("\n2. Testing Model Info...")
    try:
        metadata = predictor.metadata or {}
        print(f"✅ Model Info:")
        print(f"   Type: {predictor.model_type}")
        print(f"   Feature Count: {len(predictor.feature_columns)}")
        print(f"   Train Size: {metadata.get('train_size', 'N/A')}")
        print(f"   Validation Size: {metadata.get('val_size', 'N/A')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test single prediction
    print("\n3. Testing Single Prediction...")
    try:
        # Load a sample from test predictions
        test_predictions_path = Path("evaluation_results/test_predictions.csv")
        if test_predictions_path.exists():
            df = pd.read_csv(test_predictions_path)
            sample = df.iloc[0]
            
            # Extract features
            exclude_cols = ['claim_id', 'denial_probability', 'denial_prediction', 'risk_level']
            feature_cols = [c for c in sample.index if c not in exclude_cols]
            features = {col: float(sample[col]) if pd.notna(sample[col]) else 0.0 
                       for col in feature_cols}
            
            # Make prediction
            result = predictor.predict(
                features=features,
                return_explanations=True
            )
            
            print(f"✅ Prediction successful")
            print(f"   Claim ID: test_claim_001")
            print(f"   Probability: {result['probability']:.4f}")
            print(f"   Prediction: {result['prediction']}")
            print(f"   Risk Level: {result['risk_level']}")
            
            if result.get('feature_importance'):
                print(f"\n   Top 5 Features:")
                top = sorted(
                    result['feature_importance'].items(),
                    key=lambda x: abs(x[1]),
                    reverse=True
                )[:5]
                for feature, importance in top:
                    print(f"      {feature:40s} {importance:8.4f}")
        else:
            print("⚠️  Test predictions file not found")
            print("   Creating minimal test...")
            
            # Create minimal features dict (all zeros)
            features = {col: 0.0 for col in predictor.feature_columns}
            
            result = predictor.predict(features=features, return_explanations=False)
            print(f"✅ Prediction successful (minimal features)")
            print(f"   Probability: {result['probability']:.4f}")
            print(f"   Risk Level: {result['risk_level']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test batch prediction
    print("\n4. Testing Batch Prediction...")
    try:
        if test_predictions_path.exists():
            df = pd.read_csv(test_predictions_path)
            samples = df.head(3)
            
            exclude_cols = ['claim_id', 'denial_probability', 'denial_prediction', 'risk_level']
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            
            features_list = []
            for _, sample in samples.iterrows():
                features = {col: float(sample[col]) if pd.notna(sample[col]) else 0.0 
                           for col in feature_cols}
                features_list.append(features)
            
            features_df = pd.DataFrame(features_list)
            predictions_df = predictor.predict_batch(features_df)
            
            print(f"✅ Batch prediction successful")
            print(f"   Processed: {len(predictions_df)} claims")
            for idx, row in predictions_df.iterrows():
                print(f"   Claim {idx}: {row['denial_probability']:.4f} ({row['risk_level']})")
        else:
            print("⚠️  Test predictions file not found, skipping batch test")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ API Local Testing Complete!")
    print("=" * 60)
    print("\nTo test with actual HTTP requests:")
    print("  1. Start server: uvicorn src.api.app:app --reload")
    print("  2. Run: python scripts/test_api.py")


if __name__ == "__main__":
    test_api_locally()


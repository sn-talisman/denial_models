#!/usr/bin/env python3
"""Test the API endpoints.

Tests prediction endpoints with sample data.
"""

import requests
import json
from pathlib import Path
import pandas as pd

API_BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)
    
    response = requests.get(f"{API_BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_model_info():
    """Test model info endpoint."""
    print("=" * 60)
    print("Testing Model Info Endpoint")
    print("=" * 60)
    
    response = requests.get(f"{API_BASE_URL}/api/v1/model/info")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Model Type: {data['model_type']}")
        print(f"Feature Count: {data['feature_count']}")
        print(f"Features: {len(data['feature_columns'])}")
        print(f"Top 10 Features: {data['feature_columns'][:10]}")
    else:
        print(f"Error: {response.text}")
    print()


def test_predict():
    """Test single prediction endpoint."""
    print("=" * 60)
    print("Testing Single Prediction Endpoint")
    print("=" * 60)
    
    # Load a sample from test predictions
    test_predictions_path = Path("evaluation_results/test_predictions.csv")
    if test_predictions_path.exists():
        df = pd.read_csv(test_predictions_path)
        sample = df.iloc[0]
        
        # Extract features (exclude prediction columns)
        exclude_cols = ['claim_id', 'denial_probability', 'denial_prediction', 'risk_level']
        feature_cols = [c for c in sample.index if c not in exclude_cols]
        features = {col: float(sample[col]) if pd.notna(sample[col]) else 0.0 
                   for col in feature_cols}
        
        request_data = {
            "claim_id": "test_claim_001",
            "features": features,
            "include_explanations": True
        }
        
        print(f"Making prediction for claim: test_claim_001")
        print(f"Features: {len(features)}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/predict",
            json=request_data
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Prediction Result:")
            print(f"   Claim ID: {data['claim_id']}")
            print(f"   Denial Probability: {data['denial_probability']:.4f}")
            print(f"   Denial Prediction: {data['denial_prediction']}")
            print(f"   Risk Level: {data['risk_level']}")
            
            if data.get('feature_importance'):
                print(f"\n   Top 5 Features:")
                top_features = sorted(
                    data['feature_importance'].items(),
                    key=lambda x: abs(x[1]),
                    reverse=True
                )[:5]
                for feature, importance in top_features:
                    print(f"      {feature:40s} {importance:8.4f}")
        else:
            print(f"Error: {response.text}")
    else:
        print("⚠️  Test predictions file not found")
        print("   Creating minimal test request...")
        
        # Create minimal request with all features set to 0
        # This will test the API but may not give meaningful predictions
        request_data = {
            "claim_id": "test_claim_minimal",
            "features": {},  # Will be filled with zeros by predictor
            "include_explanations": False
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/predict",
            json=request_data
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Prediction: {data['denial_probability']:.4f}")
        else:
            print(f"Error: {response.text}")
    
    print()


def test_batch_predict():
    """Test batch prediction endpoint."""
    print("=" * 60)
    print("Testing Batch Prediction Endpoint")
    print("=" * 60)
    
    # Load samples from test predictions
    test_predictions_path = Path("evaluation_results/test_predictions.csv")
    if test_predictions_path.exists():
        df = pd.read_csv(test_predictions_path)
        samples = df.head(3)  # Test with 3 claims
        
        exclude_cols = ['claim_id', 'denial_probability', 'denial_prediction', 'risk_level']
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        
        claims = []
        for idx, sample in samples.iterrows():
            features = {col: float(sample[col]) if pd.notna(sample[col]) else 0.0 
                       for col in feature_cols}
            claims.append({
                "claim_id": f"test_claim_{idx:03d}",
                "features": features,
                "include_explanations": False
            })
        
        request_data = {
            "claims": claims,
            "max_claims": 1000
        }
        
        print(f"Making batch prediction for {len(claims)} claims...")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/predict/batch",
            json=request_data
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Batch Prediction Result:")
            print(f"   Total Processed: {data['total_processed']}")
            if data.get('errors'):
                print(f"   Errors: {len(data['errors'])}")
            
            print(f"\n   Predictions:")
            for pred in data['predictions']:
                print(f"      {pred['claim_id']}: {pred['denial_probability']:.4f} ({pred['risk_level']})")
        else:
            print(f"Error: {response.text}")
    else:
        print("⚠️  Test predictions file not found, skipping batch test")
    
    print()


def main():
    """Run all API tests."""
    print("🚀 Testing Denial Prediction API\n")
    
    try:
        test_health()
        test_model_info()
        test_predict()
        test_batch_predict()
        
        print("=" * 60)
        print("✅ API Testing Complete!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API")
        print("   Make sure the API server is running:")
        print("   uvicorn src.api.app:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


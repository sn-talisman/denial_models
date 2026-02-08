#!/usr/bin/env python3
"""Test SHAP explainability for denial predictions.

Demonstrates SHAP explanations for individual predictions and batch predictions.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.denial_predictor.predictor import DenialPredictor
from src.models.explainability.shap_explainer import SHAPExplainer

def test_shap_explanations():
    """Test SHAP explainability."""
    print("=" * 60)
    print("SHAP Explainability Test")
    print("=" * 60)
    
    # Check if SHAP is available
    try:
        import shap
        print(f"\n✅ SHAP installed (version: {shap.__version__})\n")
    except ImportError:
        print("\n❌ SHAP not installed")
        print("   Install with: pip install shap")
        return
    
    # Load model
    model_path = Path("models/denial_predictor_lightgbm.pkl")
    if not model_path.exists():
        print(f"\n❌ Model not found: {model_path}")
        print("   Please train the model first")
        return
    
    print(f"📥 Loading model from {model_path}...")
    predictor = DenialPredictor(model_path=model_path)
    print(f"✅ Model loaded ({len(predictor.feature_columns)} features)\n")
    
    # Create SHAP explainer
    print("🔧 Creating SHAP explainer...")
    try:
        shap_explainer = SHAPExplainer(
            predictor.model,
            predictor.feature_columns,
            predictor.model_type
        )
        print("✅ SHAP explainer created\n")
    except Exception as e:
        print(f"❌ Failed to create SHAP explainer: {e}")
        return
    
    # Load some test data for examples
    print("📊 Loading test predictions for examples...")
    test_predictions_path = Path("evaluation_results/test_predictions.csv")
    
    if test_predictions_path.exists():
        test_df = pd.read_csv(test_predictions_path)
        print(f"✅ Loaded {len(test_df)} test predictions\n")
        
        # Select a few examples
        # High risk example
        high_risk = test_df[test_df['denial_probability'] > 0.7].head(1)
        # Low risk example
        low_risk = test_df[test_df['denial_probability'] < 0.3].head(1)
        # Medium risk example
        medium_risk = test_df[(test_df['denial_probability'] >= 0.3) & 
                             (test_df['denial_probability'] <= 0.7)].head(1)
        
        examples = []
        if len(high_risk) > 0:
            examples.append(("High Risk", high_risk.iloc[0]))
        if len(medium_risk) > 0:
            examples.append(("Medium Risk", medium_risk.iloc[0]))
        if len(low_risk) > 0:
            examples.append(("Low Risk", low_risk.iloc[0]))
        
        # Explain each example
        for risk_level, example in examples:
            print("=" * 60)
            print(f"📋 Example: {risk_level} Claim")
            print("=" * 60)
            print(f"\nClaim ID: {example.get('claim_id', 'N/A')}")
            print(f"Predicted Probability: {example['denial_probability']:.4f}")
            print(f"Risk Level: {example['risk_level']}\n")
            
            # Get features (exclude prediction columns)
            exclude_cols = ['claim_id', 'denial_probability', 'denial_prediction', 'risk_level']
            feature_cols = [c for c in example.index if c not in exclude_cols]
            features = example[feature_cols].to_dict()
            
            # Get SHAP explanation
            print("🔍 Generating SHAP explanation...")
            try:
                explanation = shap_explainer.explain_prediction(
                    features,
                    return_values=True,
                    return_plot_data=False
                )
                
                print(f"\n📊 Prediction Details:")
                print(f"   Base Value: {explanation['base_value']:.4f}")
                print(f"   Prediction: {explanation['prediction']:.4f}")
                print(f"   SHAP Value Sum: {sum(explanation['shap_values']):.4f}")
                print(f"   (Base + SHAP Sum = {explanation['base_value'] + sum(explanation['shap_values']):.4f})")
                
                print(f"\n🏆 Top 10 Contributing Features:")
                top_features = list(explanation['feature_importance'].items())[:10]
                for i, (feature, importance) in enumerate(top_features, 1):
                    direction = "↑" if importance > 0 else "↓"
                    print(f"   {i:2d}. {feature:40s} {direction} {importance:8.4f}")
                
                # Show features pushing towards denial
                denial_features = {k: v for k, v in explanation['feature_importance'].items() if v > 0}
                approval_features = {k: v for k, v in explanation['feature_importance'].items() if v < 0}
                
                print(f"\n📈 Features Pushing Towards DENIAL (positive SHAP):")
                top_denial = sorted(denial_features.items(), key=lambda x: x[1], reverse=True)[:5]
                for feature, importance in top_denial:
                    print(f"   • {feature:40s} +{importance:8.4f}")
                
                print(f"\n📉 Features Pushing Towards APPROVAL (negative SHAP):")
                top_approval = sorted(approval_features.items(), key=lambda x: x[1])[:5]
                for feature, importance in top_approval:
                    print(f"   • {feature:40s} {importance:8.4f}")
                
                print()
                
            except Exception as e:
                print(f"❌ Error generating explanation: {e}")
                import traceback
                traceback.print_exc()
        
        # Test batch explanation
        print("=" * 60)
        print("📦 Batch SHAP Explanation")
        print("=" * 60)
        
        # Select a small batch
        batch_df = test_df.head(10)
        feature_cols = [c for c in batch_df.columns if c not in exclude_cols]
        batch_features = batch_df[feature_cols]
        
        print(f"\n🔍 Explaining {len(batch_features)} claims...")
        try:
            batch_explanation = shap_explainer.explain_batch(
                batch_features,
                max_samples=10
            )
            
            print(f"✅ Batch explanation complete\n")
            print(f"📊 Global Feature Importance (average across batch):")
            top_global = list(batch_explanation['feature_importance'].items())[:15]
            for i, (feature, importance) in enumerate(top_global, 1):
                print(f"   {i:2d}. {feature:40s} {importance:8.4f}")
            
        except Exception as e:
            print(f"❌ Error in batch explanation: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        print("⚠️  Test predictions file not found")
        print("   Run evaluation first: python scripts/evaluate_model.py")
        print("\n   Creating synthetic example instead...\n")
        
        # Create a synthetic example with all features set to 0
        features = {col: 0.0 for col in predictor.feature_columns}
        
        print("🔍 Generating SHAP explanation for synthetic claim...")
        try:
            explanation = shap_explainer.explain_prediction(features)
            
            print(f"\n📊 Prediction Details:")
            print(f"   Base Value: {explanation['base_value']:.4f}")
            print(f"   Prediction: {explanation['prediction']:.4f}")
            
            print(f"\n🏆 Top 10 Contributing Features:")
            top_features = list(explanation['feature_importance'].items())[:10]
            for i, (feature, importance) in enumerate(top_features, 1):
                print(f"   {i:2d}. {feature:40s} {importance:8.4f}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Test integration with predictor
    print("\n" + "=" * 60)
    print("🔗 Testing Predictor Integration")
    print("=" * 60)
    
    if test_predictions_path.exists() and len(test_df) > 0:
        example = test_df.iloc[0]
        feature_cols = [c for c in example.index if c not in exclude_cols]
        features = example[feature_cols].to_dict()
        
        print(f"\n🔮 Making prediction with explanations...")
        result = predictor.predict(
            features=features,
            return_explanations=True
        )
        
        print(f"✅ Prediction: {result['probability']:.4f}")
        print(f"   Risk Level: {result['risk_level']}")
        
        if 'feature_importance' in result:
            print(f"   Explanation Type: {result.get('explanation_type', 'unknown')}")
            print(f"\n🏆 Top 5 Features:")
            top = list(result['feature_importance'].items())[:5]
            for i, (feature, importance) in enumerate(top, 1):
                print(f"   {i}. {feature:40s} {importance:8.4f}")
        else:
            print("   ⚠️  No feature importance available")
    
    print("\n" + "=" * 60)
    print("✅ SHAP Testing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_shap_explanations()


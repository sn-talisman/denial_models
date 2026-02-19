#!/usr/bin/env python3
"""Evaluate trained model on test set.

Generates comprehensive metrics, confusion matrix, and error analysis.
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    roc_curve,
    precision_recall_curve,
    roc_auc_score,
    average_precision_score,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer import engineer_features_batch
from src.models.denial_predictor.trainer import prepare_training_data
from src.models.denial_predictor.predictor import DenialPredictor
from src.utils.metrics import calculate_denial_metrics
from src.utils.logging_config import configure_logging
from datetime import date, timedelta

load_dotenv()
configure_logging()


async def evaluate_model():
    """Evaluate model on test set."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        sys.exit(1)
    
    model_path = Path("models/denial_predictor_lightgbm.pkl")
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        print("   Please train the model first: python scripts/train_model.py")
        sys.exit(1)
    
    print("=" * 60)
    print("Model Evaluation on Test Set")
    print("=" * 60)
    print(f"\n📡 Database: {database_url.split('@')[1] if '@' in database_url else 'configured'}")
    print(f"📦 Model: {model_path}\n")
    
    repository = get_repository()
    
    try:
        # Fetch claims from last 365 days (same as training)
        date_to = date.today()
        date_from = date_to - timedelta(days=365)
        
        print(f"📊 Fetching claims from {date_from} to {date_to}...")
        claims = await repository.get_claims(
            date_from=date_from,
            date_to=date_to,
        )
        
        if not claims:
            print("❌ No claims found")
            return
        
        print(f"✅ Found {len(claims)} claims\n")
        
        # Engineer features
        print("🔧 Engineering features...")
        df = await engineer_features_batch(
            claims=claims,
            repository=repository,
            reference_date=date_to,
        )
        
        if df.empty:
            print("❌ No features generated")
            return
        
        print(f"✅ Generated features for {len(df)} claims\n")
        
        # Prepare training data (same split as training)
        print("📦 Preparing data splits...")
        X_train, X_val, y_train, y_val, X_test, y_test = prepare_training_data(
            df,
            target_column="is_denied",
            test_size=0.2,
            validation_size=0.1,
            random_state=42,
        )
        
        print(f"✅ Test set: {len(X_test)} claims")
        print(f"   Denied: {y_test.sum()} ({y_test.mean():.1%})")
        print(f"   Not Denied: {(~y_test.astype(bool)).sum()} ({(1-y_test.mean()):.1%})\n")
        
        # Load model
        print("📥 Loading model...")
        predictor = DenialPredictor(model_path=model_path)
        print(f"✅ Model loaded ({len(predictor.feature_columns)} features)\n")
        
        # Make predictions
        print("🔮 Making predictions...")
        predictions_df = predictor.predict_batch(X_test)
        
        y_pred = predictions_df["denial_prediction"].values.astype(int)
        y_proba = predictions_df["denial_probability"].values
        y_test_int = y_test.values.astype(int) if hasattr(y_test, 'values') else np.array(y_test).astype(int)
        
        print("✅ Predictions complete\n")
        
        # Calculate metrics
        print("=" * 60)
        print("📈 Test Set Metrics")
        print("=" * 60)
        
        metrics = calculate_denial_metrics(y_test_int, y_pred, y_proba)
        
        print(f"\n🎯 Overall Performance:")
        print(f"   Accuracy: {metrics['accuracy']:.4f}")
        print(f"   Precision: {metrics['precision']:.4f}")
        print(f"   Recall: {metrics['recall']:.4f}")
        print(f"   F1-Score: {metrics['f1_score']:.4f}")
        print(f"   ROC-AUC: {metrics['roc_auc']:.4f}")
        print(f"   PR-AUC: {metrics['pr_auc']:.4f}")
        print(f"   Brier Score: {metrics['brier_score']:.4f}")
        print(f"   ECE: {metrics['ece']:.4f}")
        
        print(f"\n📊 Confusion Matrix:")
        cm = confusion_matrix(y_test_int, y_pred)
        print(f"   True Negatives:  {cm[0,0]:5d}  |  False Positives: {cm[0,1]:5d}")
        print(f"   False Negatives: {cm[1,0]:5d}  |  True Positives:  {cm[1,1]:5d}")
        
        print(f"\n📋 Classification Report:")
        print(classification_report(y_test_int, y_pred, target_names=["Not Denied", "Denied"]))
        
        # Error analysis
        print("\n" + "=" * 60)
        print("🔍 Error Analysis")
        print("=" * 60)
        
        # False positives (predicted denied but not denied)
        false_positives = predictions_df[(y_test_int == 0) & (y_pred == 1)]
        print(f"\n❌ False Positives: {len(false_positives)}")
        if len(false_positives) > 0:
            print(f"   Average probability: {false_positives['denial_probability'].mean():.4f}")
            print(f"   Min probability: {false_positives['denial_probability'].min():.4f}")
            print(f"   Max probability: {false_positives['denial_probability'].max():.4f}")
        
        # False negatives (predicted not denied but denied)
        false_negatives = predictions_df[(y_test_int == 1) & (y_pred == 0)]
        print(f"\n❌ False Negatives: {len(false_negatives)}")
        if len(false_negatives) > 0:
            print(f"   Average probability: {false_negatives['denial_probability'].mean():.4f}")
            print(f"   Min probability: {false_negatives['denial_probability'].min():.4f}")
            print(f"   Max probability: {false_negatives['denial_probability'].max():.4f}")
        
        # High confidence errors
        high_conf_fp = false_positives[false_positives['denial_probability'] > 0.7]
        high_conf_fn = false_negatives[false_negatives['denial_probability'] < 0.3]
        
        print(f"\n⚠️  High Confidence Errors:")
        print(f"   False Positives (prob > 0.7): {len(high_conf_fp)}")
        print(f"   False Negatives (prob < 0.3): {len(high_conf_fn)}")
        
        # Risk level distribution
        print(f"\n📊 Risk Level Distribution:")
        risk_dist = predictions_df['risk_level'].value_counts()
        for level, count in risk_dist.items():
            pct = count / len(predictions_df) * 100
            print(f"   {level}: {count} ({pct:.1f}%)")
        
        # Probability distribution
        print(f"\n📊 Probability Distribution:")
        print(f"   Mean: {y_proba.mean():.4f}")
        print(f"   Median: {np.median(y_proba):.4f}")
        print(f"   Std: {y_proba.std():.4f}")
        print(f"   Min: {y_proba.min():.4f}")
        print(f"   Max: {y_proba.max():.4f}")
        
        # Percentiles
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        print(f"\n   Percentiles:")
        for p in percentiles:
            val = np.percentile(y_proba, p)
            print(f"   {p:2d}th: {val:.4f}")
        
        # Save results
        output_dir = Path("evaluation_results")
        output_dir.mkdir(exist_ok=True)
        
        # Save predictions
        predictions_df.to_csv(output_dir / "test_predictions.csv", index=False)
        print(f"\n💾 Predictions saved to: {output_dir / 'test_predictions.csv'}")
        
        # Save metrics
        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(output_dir / "test_metrics.csv", index=False)
        print(f"💾 Metrics saved to: {output_dir / 'test_metrics.csv'}")
        
        # Save confusion matrix
        cm_df = pd.DataFrame(cm, 
                            index=["Actual: Not Denied", "Actual: Denied"],
                            columns=["Predicted: Not Denied", "Predicted: Denied"])
        cm_df.to_csv(output_dir / "confusion_matrix.csv")
        print(f"💾 Confusion matrix saved to: {output_dir / 'confusion_matrix.csv'}")
        
        print("\n" + "=" * 60)
        print("✅ Evaluation Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(evaluate_model())


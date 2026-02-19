#!/usr/bin/env python3
"""Train denial prediction model.

Usage:
    python scripts/train_model.py --days-back 365 --model-type lightgbm
    python scripts/train_model.py --days-back 180 --tune --n-trials 50
"""

import asyncio
import argparse
import os
from pathlib import Path
import sys
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

# Validate DATABASE_URL early
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    print("\nPlease set it with:")
    print('  export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/tebra_dw"')
    print("\nOr create a .env file with:")
    print('  DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tebra_dw')
    sys.exit(1)

from src.data_access.factory import get_repository
from src.pipelines.pipeline_runner import PipelineRunner
from src.models.denial_predictor.trainer import (
    prepare_training_data,
    train_denial_predictor,
    save_model,
)
from src.utils.logging_config import configure_logging

configure_logging()

print(f"Using database: {database_url.split('@')[1] if '@' in database_url else 'configured'}")


async def main():
    parser = argparse.ArgumentParser(description="Train denial prediction model")
    parser.add_argument("--days-back", type=int, default=365, help="Days of historical data")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of claims")
    parser.add_argument("--model-type", choices=["xgboost", "lightgbm"], default="lightgbm")
    parser.add_argument("--tune", action="store_true", help="Use hyperparameter tuning")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of Optuna trials")
    parser.add_argument("--output-dir", type=Path, default=Path("models"), help="Output directory")
    parser.add_argument("--practice-id", type=str, default=None, help="Filter by practice ID")
    parser.add_argument("--payer-id", type=str, default=None, help="Filter by payer ID")

    args = parser.parse_args()

    repo = get_repository()
    try:
        print("Fetching training data...")
        runner = PipelineRunner(repo)
        df = await runner.run_full_pipeline(
            practice_id=args.practice_id,
            payer_id=args.payer_id,
            date_from=date.today() - timedelta(days=args.days_back),
            date_to=date.today(),
            limit=args.limit,
            include_features=True,
        )

        if len(df) < 20:
            print(f"Not enough data for training (need >=20, got {len(df)})")
            return 1

        if "is_denied" not in df.columns:
            print("No 'is_denied' column found in features")
            return 1

        denied_count = df["is_denied"].sum()
        denied_rate = denied_count / len(df)
        print(f"\nTraining Data: {len(df)} claims, {len(df.columns)} features")
        print(f"Denied claims: {denied_count} ({denied_rate:.1%})")

        print("\nPreparing train/validation/test splits...")
        X_train, X_val, y_train, y_val, X_test, y_test = prepare_training_data(
            df,
            target_column="is_denied",
            test_size=0.2,
            validation_size=0.1,
            random_state=42,
        )
        print(f"  Train: {len(X_train)}, Validation: {len(X_val)}, Test: {len(X_test)}")

        print(f"\nTraining {args.model_type} model...")
        if args.tune:
            print(f"  Hyperparameter tuning enabled ({args.n_trials} trials)")
        model, metrics = train_denial_predictor(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            model_type=args.model_type,
            use_hyperparameter_tuning=args.tune,
            n_trials=args.n_trials,
            calibrate=True,
        )

        print("\nTraining Complete!")
        _print_metrics("Training Metrics", metrics.get("train", {}))
        _print_metrics("Validation Metrics", metrics.get("validation", {}))

        args.output_dir.mkdir(parents=True, exist_ok=True)
        model_path = args.output_dir / f"denial_predictor_{args.model_type}.pkl"

        save_model(
            model=model,
            model_path=model_path,
            feature_columns=list(X_train.columns),
            metadata={
                "model_type": args.model_type,
                "train_size": len(X_train),
                "val_size": len(X_val),
                "test_size": len(X_test),
                "metrics": metrics,
                "days_back": args.days_back,
            },
        )
        print(f"\nModel saved to: {model_path}")
        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await repo.close()


def _print_metrics(title: str, m: dict):
    """Pretty-print a metrics dict, skipping raw counts."""
    if not m:
        return
    skip = {"true_positives", "true_negatives", "false_positives", "false_negatives"}
    print(f"\n{title}:")
    for k, v in m.items():
        if isinstance(v, (int, float)) and k not in skip:
            print(f"  {k}: {v:.4f}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

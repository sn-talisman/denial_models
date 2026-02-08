#!/usr/bin/env python3
"""Analyze denials and rejections by practice and payer.

Provides comprehensive analysis including:
- Denial/rejection rates by practice
- Denial/rejection rates by payer
- Practice-payer combinations
- Model predictions for each group
- Risk level distributions
"""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer_optimized import engineer_features_batch_optimized as engineer_features_batch
from src.models.denial_predictor.predictor import DenialPredictor
from src.utils.logging_config import configure_logging

load_dotenv()
configure_logging()


async def analyze_practice_payer():
    """Analyze denials and rejections by practice and payer."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        sys.exit(1)
    
    model_path = Path("models/denial_predictor_lightgbm.pkl")
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        print("   Please train the model first")
        sys.exit(1)
    
    print("=" * 60)
    print("Practice & Payer Denial Analysis")
    print("=" * 60)
    print(f"\n📡 Database: {database_url.split('@')[1] if '@' in database_url else 'configured'}")
    print(f"📦 Model: {model_path}\n")
    
    repository = get_repository()
    predictor = DenialPredictor(model_path=model_path)
    
    try:
        # Fetch claims from last 365 days
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
        print("🔧 Engineering features (this may take a moment for large datasets)...")
        print("   Progress will be shown below:\n")
        df = await engineer_features_batch(
            claims=claims,
            repository=repository,
            reference_date=date_to,
        )
        
        if df.empty:
            print("❌ No features generated")
            return
        
        print(f"\n✅ Generated features for {len(df)} claims\n")
        
        # Make predictions
        print("🔮 Making predictions (this is fast - <1 second)...")
        exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                       'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                       'cpt_code', 'cpt_category', 'is_denied']
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        features_df = df[feature_cols].copy()
        
        # Convert object columns to numeric
        for col in features_df.columns:
            if features_df[col].dtype == 'object':
                try:
                    features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
                except:
                    pass
        
        # Fill NaN values and ensure numeric types
        features_df = features_df.fillna(0)
        for col in features_df.columns:
            if features_df[col].dtype == 'object':
                features_df[col] = features_df[col].astype(float)
        
        predictions_df = predictor.predict_batch(features_df)
        
        # Create mapping from claim_id to practice_id and payer_id
        claim_to_practice = {c.claim_id: c.practice_id for c in claims}
        claim_to_payer = {c.claim_id: c.payer_id for c in claims}
        
        # Add original data
        predictions_df['claim_id'] = df['claim_id'].values
        predictions_df['practice_id'] = predictions_df['claim_id'].map(claim_to_practice)
        predictions_df['payer_id'] = predictions_df['claim_id'].map(claim_to_payer)
        predictions_df['is_denied'] = df['is_denied'].values if 'is_denied' in df.columns else [False] * len(df)
        predictions_df['is_rejected'] = df['is_rejected'].values if 'is_rejected' in df.columns else [False] * len(df)
        predictions_df['total_billed_amount'] = df['total_billed_amount'].values if 'total_billed_amount' in df.columns else [0] * len(df)
        
        print("✅ Predictions complete\n")
        
        # Get practice and payer names
        print("📋 Fetching practice and payer names...")
        practices = await repository.get_practices()
        payers = await repository.get_payers()
        
        practice_map = {p.practice_id: p.name for p in practices}
        payer_map = {p.payer_id: p.name for p in payers}
        
        # Map practice names, fallback to practice_id if not found
        predictions_df['practice_name'] = predictions_df['practice_id'].map(practice_map)
        # For missing names, use practice_id as fallback
        missing_practice_mask = predictions_df['practice_name'].isna() & predictions_df['practice_id'].notna()
        predictions_df.loc[missing_practice_mask, 'practice_name'] = 'Practice ' + predictions_df.loc[missing_practice_mask, 'practice_id'].astype(str).str[:8]
        
        predictions_df['payer_name'] = predictions_df['payer_id'].map(payer_map)
        # For missing payer names, use payer_id as fallback
        missing_payer_mask = predictions_df['payer_name'].isna() & predictions_df['payer_id'].notna()
        predictions_df.loc[missing_payer_mask, 'payer_name'] = 'Payer ' + predictions_df.loc[missing_payer_mask, 'payer_id'].astype(str).str[:20]
        
        print(f"✅ Names loaded ({len(practices)} practices, {len(payers)} payers)\n")
        
        # Analyze by Practice
        print("📊 Analyzing by practice...")
        
        practice_analysis = []
        for practice_id in predictions_df['practice_id'].dropna().unique():
            practice_data = predictions_df[predictions_df['practice_id'] == practice_id]
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            total = len(practice_data)
            denied = practice_data['is_denied'].sum()
            rejected = practice_data['is_rejected'].sum()
            denied_or_rejected = (practice_data['is_denied'] | practice_data['is_rejected']).sum()
            
            # Model predictions
            high_risk = (practice_data['risk_level'] == 'high').sum()
            medium_risk = (practice_data['risk_level'] == 'medium').sum()
            low_risk = (practice_data['risk_level'] == 'low').sum()
            avg_probability = practice_data['denial_probability'].mean()
            
            # Financial impact
            total_billed = practice_data['total_billed_amount'].sum()
            denied_billed = practice_data[practice_data['is_denied']]['total_billed_amount'].sum()
            
            practice_analysis.append({
                'practice_id': practice_id,
                'practice_name': practice_name,
                'total_claims': total,
                'denied_claims': denied,
                'rejected_claims': rejected,
                'denied_or_rejected': denied_or_rejected,
                'denial_rate': denied / total if total > 0 else 0,
                'rejection_rate': rejected / total if total > 0 else 0,
                'denial_or_rejection_rate': denied_or_rejected / total if total > 0 else 0,
                'avg_denial_probability': avg_probability,
                'high_risk_count': high_risk,
                'medium_risk_count': medium_risk,
                'low_risk_count': low_risk,
                'high_risk_pct': high_risk / total if total > 0 else 0,
                'total_billed': total_billed,
                'denied_billed': denied_billed,
                'denied_billed_pct': denied_billed / total_billed if total_billed > 0 else 0,
            })
        
        practice_df = pd.DataFrame(practice_analysis)
        practice_df = practice_df.sort_values('denial_rate', ascending=False)
        
        print(f"✅ Analyzed {len(practice_df)} practices\n")
        
        print("=" * 60)
        print("📊 Analysis by Practice")
        print("=" * 60)
        print(f"\n📈 Top 10 Practices by Denial Rate:")
        print(f"{'Practice Name':<40} {'Claims':<8} {'Denied':<8} {'Rate':<8} {'Avg Prob':<10} {'High Risk':<10}")
        print("-" * 100)
        for _, row in practice_df.head(10).iterrows():
            practice_name = str(row['practice_name']) if pd.notna(row['practice_name']) else "Unknown"
            print(f"{practice_name[:39]:<40} {row['total_claims']:<8} {row['denied_claims']:<8} "
                  f"{row['denial_rate']:<8.1%} {row['avg_denial_probability']:<10.3f} {row['high_risk_pct']:<10.1%}")
        
        # Analysis by Payer
        print("\n📊 Analyzing by payer...")
        payer_analysis = []
        for payer_id in predictions_df['payer_id'].dropna().unique():
            payer_data = predictions_df[predictions_df['payer_id'] == payer_id]
            payer_name = payer_data['payer_name'].iloc[0] if len(payer_data) > 0 else "Unknown"
            
            total = len(payer_data)
            denied = payer_data['is_denied'].sum()
            rejected = payer_data['is_rejected'].sum()
            denied_or_rejected = (payer_data['is_denied'] | payer_data['is_rejected']).sum()
            
            # Model predictions
            high_risk = (payer_data['risk_level'] == 'high').sum()
            medium_risk = (payer_data['risk_level'] == 'medium').sum()
            low_risk = (payer_data['risk_level'] == 'low').sum()
            avg_probability = payer_data['denial_probability'].mean()
            
            # Financial impact
            total_billed = payer_data['total_billed_amount'].sum()
            denied_billed = payer_data[payer_data['is_denied']]['total_billed_amount'].sum()
            
            payer_analysis.append({
                'payer_id': payer_id,
                'payer_name': payer_name,
                'total_claims': total,
                'denied_claims': denied,
                'rejected_claims': rejected,
                'denied_or_rejected': denied_or_rejected,
                'denial_rate': denied / total if total > 0 else 0,
                'rejection_rate': rejected / total if total > 0 else 0,
                'denial_or_rejection_rate': denied_or_rejected / total if total > 0 else 0,
                'avg_denial_probability': avg_probability,
                'high_risk_count': high_risk,
                'medium_risk_count': medium_risk,
                'low_risk_count': low_risk,
                'high_risk_pct': high_risk / total if total > 0 else 0,
                'total_billed': total_billed,
                'denied_billed': denied_billed,
                'denied_billed_pct': denied_billed / total_billed if total_billed > 0 else 0,
            })
        
        payer_df = pd.DataFrame(payer_analysis)
        payer_df = payer_df.sort_values('denial_rate', ascending=False)
        
        print(f"✅ Analyzed {len(payer_df)} payers\n")
        
        print("=" * 60)
        print("📊 Analysis by Payer")
        print("=" * 60)
        print(f"\n📈 Top 10 Payers by Denial Rate:")
        print(f"{'Payer Name':<40} {'Claims':<8} {'Denied':<8} {'Rate':<8} {'Avg Prob':<10} {'High Risk':<10}")
        print("-" * 100)
        for _, row in payer_df.head(10).iterrows():
            payer_name = str(row['payer_name']) if pd.notna(row['payer_name']) else "Unknown"
            print(f"{payer_name[:39]:<40} {row['total_claims']:<8} {row['denied_claims']:<8} "
                  f"{row['denial_rate']:<8.1%} {row['avg_denial_probability']:<10.3f} {row['high_risk_pct']:<10.1%}")
        
        # Practice-Payer Combinations
        print("\n📊 Analyzing practice-payer combinations...")
        combo_analysis = []
        for (practice_id, payer_id), combo_data in predictions_df.groupby(['practice_id', 'payer_id']):
            if pd.isna(practice_id) or pd.isna(payer_id):
                continue
            
            practice_name = combo_data['practice_name'].iloc[0] if len(combo_data) > 0 else "Unknown"
            payer_name = combo_data['payer_name'].iloc[0] if len(combo_data) > 0 else "Unknown"
            
            total = len(combo_data)
            if total < 5:  # Skip small combinations
                continue
            
            denied = combo_data['is_denied'].sum()
            rejected = combo_data['is_rejected'].sum()
            denied_or_rejected = (combo_data['is_denied'] | combo_data['is_rejected']).sum()
            
            avg_probability = combo_data['denial_probability'].mean()
            high_risk = (combo_data['risk_level'] == 'high').sum()
            
            total_billed = combo_data['total_billed_amount'].sum()
            denied_billed = combo_data[combo_data['is_denied']]['total_billed_amount'].sum()
            
            combo_analysis.append({
                'practice_id': practice_id,
                'practice_name': practice_name,
                'payer_id': payer_id,
                'payer_name': payer_name,
                'total_claims': total,
                'denied_claims': denied,
                'rejected_claims': rejected,
                'denied_or_rejected': denied_or_rejected,
                'denial_rate': denied / total if total > 0 else 0,
                'rejection_rate': rejected / total if total > 0 else 0,
                'denial_or_rejection_rate': denied_or_rejected / total if total > 0 else 0,
                'avg_denial_probability': avg_probability,
                'high_risk_count': high_risk,
                'high_risk_pct': high_risk / total if total > 0 else 0,
                'total_billed': total_billed,
                'denied_billed': denied_billed,
                'denied_billed_pct': denied_billed / total_billed if total_billed > 0 else 0,
            })
        
        combo_df = pd.DataFrame(combo_analysis)
        combo_df = combo_df.sort_values('denial_rate', ascending=False)
        
        print(f"✅ Analyzed {len(combo_df)} practice-payer combinations\n")
        
        print("=" * 60)
        print("📊 Analysis by Practice-Payer Combination")
        print("=" * 60)
        print(f"\n📈 Top 15 Practice-Payer Combinations by Denial Rate:")
        print(f"{'Practice':<25} {'Payer':<25} {'Claims':<8} {'Denied':<8} {'Rate':<8} {'Avg Prob':<10} {'High Risk':<10}")
        print("-" * 120)
        for _, row in combo_df.head(15).iterrows():
            practice_name = str(row['practice_name']) if pd.notna(row['practice_name']) else "Unknown"
            payer_name = str(row['payer_name']) if pd.notna(row['payer_name']) else "Unknown"
            print(f"{practice_name[:24]:<25} {payer_name[:24]:<25} {row['total_claims']:<8} "
                  f"{row['denied_claims']:<8} {row['denial_rate']:<8.1%} {row['avg_denial_probability']:<10.3f} "
                  f"{row['high_risk_pct']:<10.1%}")
        
        # Summary Statistics
        print("\n" + "=" * 60)
        print("📊 Summary Statistics")
        print("=" * 60)
        
        print(f"\nOverall:")
        print(f"   Total Claims: {len(predictions_df):,}")
        print(f"   Denied: {predictions_df['is_denied'].sum():,} ({predictions_df['is_denied'].mean():.1%})")
        print(f"   Rejected: {predictions_df['is_rejected'].sum():,} ({predictions_df['is_rejected'].mean():.1%})")
        print(f"   Denied or Rejected: {(predictions_df['is_denied'] | predictions_df['is_rejected']).sum():,} "
              f"({(predictions_df['is_denied'] | predictions_df['is_rejected']).mean():.1%})")
        
        print(f"\nModel Predictions:")
        print(f"   Average Denial Probability: {predictions_df['denial_probability'].mean():.4f}")
        print(f"   High Risk Claims: {(predictions_df['risk_level'] == 'high').sum():,} "
              f"({(predictions_df['risk_level'] == 'high').mean():.1%})")
        print(f"   Medium Risk Claims: {(predictions_df['risk_level'] == 'medium').sum():,} "
              f"({(predictions_df['risk_level'] == 'medium').mean():.1%})")
        print(f"   Low Risk Claims: {(predictions_df['risk_level'] == 'low').sum():,} "
              f"({(predictions_df['risk_level'] == 'low').mean():.1%})")
        
        print(f"\nFinancial Impact:")
        total_billed_all = predictions_df['total_billed_amount'].sum()
        denied_billed_all = predictions_df[predictions_df['is_denied']]['total_billed_amount'].sum()
        print(f"   Total Billed: ${total_billed_all:,.2f}")
        print(f"   Denied Amount: ${denied_billed_all:,.2f}")
        print(f"   Denied Percentage: {denied_billed_all / total_billed_all * 100:.2f}%")
        
        # Save results
        output_dir = Path("analysis_results")
        output_dir.mkdir(exist_ok=True)
        
        practice_df.to_csv(output_dir / "practice_analysis.csv", index=False)
        payer_df.to_csv(output_dir / "payer_analysis.csv", index=False)
        combo_df.to_csv(output_dir / "practice_payer_analysis.csv", index=False)
        predictions_df.to_csv(output_dir / "all_predictions_with_analysis.csv", index=False)
        
        print(f"\n💾 Results saved to {output_dir}/")
        print(f"   - practice_analysis.csv")
        print(f"   - payer_analysis.csv")
        print(f"   - practice_payer_analysis.csv")
        print(f"   - all_predictions_with_analysis.csv")
        
        print("\n" + "=" * 60)
        print("✅ Analysis Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(analyze_practice_payer())


#!/usr/bin/env python3
"""Test partial payment handling and feature extraction.

This script tests:
1. Partial payment detection
2. CARC/RARC code extraction
3. Adjustment amount calculation
4. Feature engineering for partially paid claims
"""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer import engineer_features_batch
from src.utils.logging_config import configure_logging

load_dotenv()
configure_logging()

async def test_partial_payments():
    """Test partial payment feature extraction."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        sys.exit(1)
    
    print("🔍 Testing Partial Payment Handling\n")
    print(f"📡 Database: {database_url.split('@')[1] if '@' in database_url else 'configured'}\n")
    
    repository = get_repository(database_url)
    
    try:
        # Fetch claims from last 90 days
        date_to = date.today()
        date_from = date_to - timedelta(days=90)
        
        print(f"📊 Fetching claims from {date_from} to {date_to}...")
        claims = await repository.get_claims(
            date_from=date_from,
            date_to=date_to,
            limit=100  # Test with 100 claims
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
        
        print(f"✅ Generated features for {len(df)} claims")
        print(f"   Total features: {len(df.columns)}\n")
        
        # Analyze payment status
        print("=" * 60)
        print("📈 Payment Status Analysis")
        print("=" * 60)
        
        # Check for payment ratio column
        if "payment_ratio" in df.columns:
            print(f"\nPayment Ratio Statistics:")
            print(f"  Mean: {df['payment_ratio'].mean():.3f}")
            print(f"  Min: {df['payment_ratio'].min():.3f}")
            print(f"  Max: {df['payment_ratio'].max():.3f}")
            print(f"  Median: {df['payment_ratio'].median():.3f}")
        
        # Count payment categories
        if "is_partially_paid" in df.columns:
            fully_paid = (df["payment_ratio"] >= 1.0).sum() if "payment_ratio" in df.columns else 0
            partially_paid = df["is_partially_paid"].sum()
            not_paid = ((df["payment_ratio"] == 0.0) | (df["payment_ratio"].isna())).sum() if "payment_ratio" in df.columns else 0
            
            print(f"\nPayment Categories:")
            print(f"  Fully Paid: {fully_paid} ({fully_paid/len(df)*100:.1f}%)")
            print(f"  Partially Paid: {partially_paid} ({partially_paid/len(df)*100:.1f}%)")
            print(f"  Not Paid: {not_paid} ({not_paid/len(df)*100:.1f}%)")
        
        # Check denial status
        if "is_denied" in df.columns:
            denied_count = df["is_denied"].sum()
            print(f"\nDenial Status:")
            print(f"  Denied: {denied_count} ({denied_count/len(df)*100:.1f}%)")
            print(f"  Not Denied: {len(df) - denied_count} ({(len(df) - denied_count)/len(df)*100:.1f}%)")
        
        # Check partial denial features
        print("\n" + "=" * 60)
        print("🔍 Partial Payment Features")
        print("=" * 60)
        
        partial_features = [
            "is_partially_paid",
            "adjustment_amount",
            "adjustment_ratio",
            "has_partial_denial",
            "denial_detail_count",
            "has_adjustments",
            "unique_carc_count",
            "unique_rarc_count",
            "total_adjustment_from_details",
        ]
        
        for feature in partial_features:
            if feature in df.columns:
                if df[feature].dtype in ['int64', 'float64']:
                    non_zero = (df[feature] != 0).sum() if df[feature].dtype == 'float64' else (df[feature] > 0).sum()
                    print(f"\n{feature}:")
                    print(f"  Present: {non_zero} claims ({non_zero/len(df)*100:.1f}%)")
                    if non_zero > 0:
                        print(f"  Mean: {df[feature].mean():.3f}")
                        print(f"  Max: {df[feature].max():.3f}")
                elif df[feature].dtype == 'bool':
                    true_count = df[feature].sum()
                    print(f"\n{feature}:")
                    print(f"  True: {true_count} claims ({true_count/len(df)*100:.1f}%)")
        
        # Show examples of partially paid claims
        print("\n" + "=" * 60)
        print("📋 Example Partially Paid Claims")
        print("=" * 60)
        
        if "is_partially_paid" in df.columns:
            partial_claims = df[df["is_partially_paid"] == True]
            
            if len(partial_claims) > 0:
                print(f"\nFound {len(partial_claims)} partially paid claims\n")
                
                # Show first 5 examples
                for idx, (_, row) in enumerate(partial_claims.head(5).iterrows()):
                    print(f"\nExample {idx + 1}:")
                    print(f"  Claim ID: {row.get('claim_id', 'N/A')}")
                    if "payment_ratio" in row:
                        print(f"  Payment Ratio: {row['payment_ratio']:.3f}")
                    if "adjustment_amount" in row:
                        print(f"  Adjustment Amount: ${row['adjustment_amount']:.2f}")
                    if "adjustment_ratio" in row:
                        print(f"  Adjustment Ratio: {row['adjustment_ratio']:.3f}")
                    if "denial_detail_count" in row:
                        print(f"  Denial Details: {row['denial_detail_count']}")
                    if "unique_carc_count" in row:
                        print(f"  Unique CARC Codes: {row['unique_carc_count']}")
                    if "unique_rarc_count" in row:
                        print(f"  Unique RARC Codes: {row['unique_rarc_count']}")
                    if "total_adjustment_from_details" in row:
                        print(f"  Total Adjustment from Details: ${row['total_adjustment_from_details']:.2f}")
            else:
                print("\n⚠️  No partially paid claims found in sample")
        else:
            print("\n⚠️  'is_partially_paid' feature not found")
        
        # Show examples with CARC/RARC codes
        print("\n" + "=" * 60)
        print("🏷️  Claims with CARC/RARC Codes")
        print("=" * 60)
        
        if "unique_carc_count" in df.columns or "unique_rarc_count" in df.columns:
            has_carc = df["unique_carc_count"] > 0 if "unique_carc_count" in df.columns else pd.Series([False] * len(df))
            has_rarc = df["unique_rarc_count"] > 0 if "unique_rarc_count" in df.columns else pd.Series([False] * len(df))
            has_codes = has_carc | has_rarc
            
            if has_codes.sum() > 0:
                print(f"\nFound {has_codes.sum()} claims with CARC/RARC codes\n")
                
                coded_claims = df[has_codes].head(5)
                for idx, (_, row) in enumerate(coded_claims.iterrows()):
                    print(f"\nExample {idx + 1}:")
                    print(f"  Claim ID: {row.get('claim_id', 'N/A')}")
                    if "unique_carc_count" in row:
                        print(f"  CARC Codes: {row['unique_carc_count']}")
                    if "unique_rarc_count" in row:
                        print(f"  RARC Codes: {row['unique_rarc_count']}")
                    if "denial_detail_count" in row:
                        print(f"  Total Denial Details: {row['denial_detail_count']}")
                    if "is_partially_paid" in row:
                        print(f"  Partially Paid: {row['is_partially_paid']}")
                    if "is_denied" in row:
                        print(f"  Denied: {row['is_denied']}")
            else:
                print("\n⚠️  No claims with CARC/RARC codes found in sample")
        
        # Summary
        print("\n" + "=" * 60)
        print("✅ Test Summary")
        print("=" * 60)
        print(f"\n✅ Successfully processed {len(df)} claims")
        print(f"✅ Generated {len(df.columns)} features")
        
        missing_features = [f for f in partial_features if f not in df.columns]
        if missing_features:
            print(f"\n⚠️  Missing features: {', '.join(missing_features)}")
        else:
            print(f"\n✅ All partial payment features present")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repository.close()

if __name__ == "__main__":
    asyncio.run(test_partial_payments())


#!/usr/bin/env python3
"""Test the analytics API endpoints locally without starting a server."""

import sys
from pathlib import Path
import asyncio
import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from src.api.routes.analytics import (
    analyze_practices,
    analyze_payers,
    analyze_practice_payer_combos,
)
from src.api.routes.predictions import get_predictor


async def test_analytics():
    """Test all analytics endpoints."""
    print("=" * 60)
    print("Testing Analytics API Endpoints")
    print("=" * 60)
    
    predictor = get_predictor()
    
    # Test practice analysis
    print("\n📊 Testing Practice Analysis...")
    try:
        practices = await analyze_practices(
            days_back=365,
            min_claims=5,
            predictor=predictor,
        )
        print(f"✅ Found {len(practices)} practices")
        if practices:
            top = practices[0]
            print(f"   Top practice: {top.practice_name}")
            print(f"   - Denial rate: {top.denial_rate:.1%}")
            print(f"   - Avg probability: {top.avg_denial_probability:.3f}")
            print(f"   - High risk: {top.high_risk_pct:.1%}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test payer analysis
    print("\n📊 Testing Payer Analysis...")
    try:
        payers = await analyze_payers(
            days_back=365,
            min_claims=5,
            predictor=predictor,
        )
        print(f"✅ Found {len(payers)} payers")
        if payers:
            top = payers[0]
            print(f"   Top payer: {top.payer_name}")
            print(f"   - Denial rate: {top.denial_rate:.1%}")
            print(f"   - Avg probability: {top.avg_denial_probability:.3f}")
            print(f"   - High risk: {top.high_risk_pct:.1%}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test practice-payer combinations
    print("\n📊 Testing Practice-Payer Combinations...")
    try:
        combos = await analyze_practice_payer_combos(
            days_back=365,
            min_claims=5,
            predictor=predictor,
        )
        print(f"✅ Found {len(combos)} combinations")
        if combos:
            top = combos[0]
            print(f"   Top combination: {top.practice_name} + {top.payer_name}")
            print(f"   - Denial rate: {top.denial_rate:.1%}")
            print(f"   - Avg probability: {top.avg_denial_probability:.3f}")
            print(f"   - High risk: {top.high_risk_pct:.1%}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Analytics API Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_analytics())


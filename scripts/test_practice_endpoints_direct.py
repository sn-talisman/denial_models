#!/usr/bin/env python3
"""Test practice analytics endpoints directly (without HTTP server)."""

import asyncio
import sys
import json
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
from src.models.denial_predictor.predictor import DenialPredictor
from src.api.analytics_helpers import (
    get_practice_data,
    calculate_performance_summary,
    get_prioritized_action_items,
    get_payer_performance,
    get_cpt_performance,
    get_high_risk_claims,
)
import structlog

load_dotenv()
structlog.configure()


async def test_endpoint_direct(practice_guid: str, days_back: int, endpoint_name: str, test_func):
    """Test an endpoint function directly."""
    print(f"\n{'='*70}")
    print(f"Testing: {endpoint_name}")
    print(f"Practice GUID: {practice_guid}")
    print(f"Days Back: {days_back}")
    print(f"{'='*70}")
    
    try:
        repository = get_repository()
        model_path = Path("models/denial_predictor_lightgbm.pkl")
        
        if not model_path.exists():
            print(f"❌ Model not found: {model_path}")
            return False, None
        
        predictor = DenialPredictor(model_path=model_path)
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                print(f"❌ No data found for practice {practice_guid}")
                return False, None
            
            # Run the test function
            result = test_func(practice_data)
            
            print(f"✅ Success!")
            print(f"\nResult Summary:")
            
            if isinstance(result, dict):
                print(f"  Keys: {list(result.keys())}")
                for key, value in result.items():
                    if isinstance(value, (int, float, str, bool)):
                        print(f"  {key}: {value}")
                    elif isinstance(value, list):
                        print(f"  {key}: {len(value)} items")
                    else:
                        print(f"  {key}: {type(value).__name__}")
            elif isinstance(result, list):
                print(f"  Items: {len(result)}")
                if result:
                    print(f"  First item keys: {list(result[0].keys()) if isinstance(result[0], dict) else 'N/A'}")
            
            # Print full result (truncated if too long)
            result_str = json.dumps(result, indent=2, default=str)
            if len(result_str) > 2000:
                print(f"\nResult (first 2000 chars):")
                print(result_str[:2000])
                print("\n... (truncated)")
            else:
                print(f"\nFull Result:")
                print(result_str)
            
            return True, result
            
        finally:
            await repository.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def main():
    """Main test function."""
    print("🧪 Testing Practice Analytics Endpoints (Direct)")
    print("="*70)
    
    # Get practice GUID
    print("\n1. Getting practice GUID from database...")
    repository = get_repository()
    
    try:
        practices = await repository.get_practices()
        if not practices:
            print("❌ No practices found")
            return
        
        date_to = date.today()
        date_from = date_to - timedelta(days=365)
        
        practice_guid = None
        for practice in practices[:5]:
            claims = await repository.get_claims(
                practice_id=practice.practice_id,
                date_from=date_from,
                date_to=date_to,
                limit=10
            )
            if claims:
                print(f"✅ Found practice: {practice.name} ({practice.practice_id})")
                practice_guid = practice.practice_id
                break
        
        if not practice_guid:
            print("⚠️  No practices with claims found, using first practice")
            practice_guid = practices[0].practice_id
    finally:
        await repository.close()
    
    if not practice_guid:
        print("❌ Cannot proceed without a practice GUID")
        return
    
    days_back = 365
    
    # Test each endpoint
    tests = [
        (
            "Performance Summary",
            lambda data: {
                **calculate_performance_summary(data, 0.24, 0.10),
                "practice_id": practice_guid,
                "practice_name": data['practice_name'].iloc[0] if len(data) > 0 else "Unknown"
            }
        ),
        (
            "Prioritized Action Items",
            lambda data: {
                "practice_id": practice_guid,
                "practice_name": data['practice_name'].iloc[0] if len(data) > 0 else "Unknown",
                "action_items": get_prioritized_action_items(data)
            }
        ),
        (
            "Performance by Payer",
            lambda data: {
                "practice_id": practice_guid,
                "practice_name": data['practice_name'].iloc[0] if len(data) > 0 else "Unknown",
                "payers": get_payer_performance(data)
            }
        ),
        (
            "Performance by CPT Code",
            lambda data: {
                "practice_id": practice_guid,
                "practice_name": data['practice_name'].iloc[0] if len(data) > 0 else "Unknown",
                "cpt_codes": get_cpt_performance(data)
            }
        ),
        (
            "High Risk Claims",
            lambda data: {
                "practice_id": practice_guid,
                "practice_name": data['practice_name'].iloc[0] if len(data) > 0 else "Unknown",
                "high_risk_claims": get_high_risk_claims(data, limit=20)
            }
        ),
    ]
    
    results = {}
    for endpoint_name, test_func in tests:
        success, data = await test_endpoint_direct(practice_guid, days_back, endpoint_name, test_func)
        results[endpoint_name] = {"success": success, "data": data}
    
    # Summary
    print(f"\n{'='*70}")
    print("Test Summary")
    print(f"{'='*70}")
    
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)
    
    for endpoint_name, result in results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{status}: {endpoint_name}")
    
    print(f"\nResults: {passed}/{total} endpoints passed")
    
    if passed == total:
        print("\n🎉 All endpoints are working correctly!")
    else:
        print("\n⚠️  Some endpoints failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())


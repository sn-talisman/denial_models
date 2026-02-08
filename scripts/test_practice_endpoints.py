#!/usr/bin/env python3
"""Test and validate the new practice analytics API endpoints."""

import asyncio
import sys
import json
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
import structlog

load_dotenv()
structlog.configure()


async def get_practice_guid():
    """Get a practice GUID from the database for testing."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        return None
    
    repository = get_repository()
    
    try:
        # Get practices
        practices = await repository.get_practices()
        
        if not practices:
            print("❌ No practices found in database")
            return None
        
        # Get a practice with claims
        date_to = date.today()
        date_from = date_to - timedelta(days=365)
        
        for practice in practices[:5]:  # Try first 5 practices
            claims = await repository.get_claims(
                practice_id=practice.practice_id,
                date_from=date_from,
                date_to=date_to,
                limit=10
            )
            if claims:
                print(f"✅ Found practice with claims: {practice.name} ({practice.practice_id})")
                return practice.practice_id
        
        print("⚠️  No practices with claims found, using first practice GUID")
        return practices[0].practice_id
        
    except Exception as e:
        print(f"❌ Error getting practice GUID: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await repository.close()


def test_endpoint(base_url: str, endpoint: str, description: str):
    """Test an API endpoint using requests."""
    import requests
    
    url = f"{base_url}{endpoint}"
    print(f"\n{'='*70}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"{'='*70}")
    
    try:
        response = requests.get(url, timeout=120)  # 2 minute timeout for analysis
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Success! Status: {response.status_code}")
        print(f"\nResponse Summary:")
        print(f"  Keys: {list(data.keys())}")
        
        # Print key metrics
        if 'total_claims' in data:
            print(f"  Total Claims: {data['total_claims']}")
        if 'denial_rate' in data:
            print(f"  Denial Rate: {data['denial_rate']:.2%}")
        if 'action_items' in data:
            print(f"  Action Items: {len(data['action_items'])}")
        if 'payers' in data:
            print(f"  Payers: {len(data['payers'])}")
        if 'cpt_codes' in data:
            print(f"  CPT Codes: {len(data['cpt_codes'])}")
        if 'high_risk_claims' in data:
            if isinstance(data['high_risk_claims'], list):
                print(f"  High Risk Claims: {len(data['high_risk_claims'])}")
            else:
                print(f"  High Risk Claims: {data['high_risk_claims']}")
        
        # Print full response (truncated if too long)
        response_str = json.dumps(data, indent=2)
        if len(response_str) > 1000:
            print(f"\nResponse (first 1000 chars):")
            print(response_str[:1000])
            print("\n... (truncated)")
        else:
            print(f"\nFull Response:")
            print(response_str)
        
        return True, data
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout: Request took longer than 120 seconds")
        return False, None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return False, None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def validate_response(data: dict, expected_keys: list, endpoint_name: str):
    """Validate response structure."""
    if data is None:
        return False
    
    missing_keys = [key for key in expected_keys if key not in data]
    if missing_keys:
        print(f"⚠️  Validation Warning for {endpoint_name}: Missing keys: {missing_keys}")
        return False
    
    print(f"✅ Validation passed for {endpoint_name}")
    return True


async def main():
    """Main test function."""
    print("🧪 Testing Practice Analytics API Endpoints")
    print("="*70)
    
    # Get practice GUID
    print("\n1. Getting practice GUID from database...")
    practice_guid = await get_practice_guid()
    
    if not practice_guid:
        print("❌ Cannot proceed without a practice GUID")
        return
    
    print(f"✅ Using practice GUID: {practice_guid}")
    
    # Check if server is running
    base_url = "http://localhost:8001"  # Using port 8001 to avoid conflicts
    import requests
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        print(f"\n✅ API server is running at {base_url}")
    except Exception as e:
        print(f"\n❌ API server is not running at {base_url}")
        print(f"   Error: {e}")
        print(f"\n   Please start the server with:")
        print(f"   uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8001")
        return
    
    # Test endpoints
    endpoints = [
        (
            f"/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=365",
            "Performance Summary",
            ["practice_id", "practice_name", "total_claims", "denial_rate", "total_billed", "denied_amount"]
        ),
        (
            f"/api/v1/analytics/practice/{practice_guid}/action-items?days_back=365",
            "Prioritized Action Items",
            ["practice_id", "practice_name", "action_items"]
        ),
        (
            f"/api/v1/analytics/practice/{practice_guid}/payer-performance?days_back=365",
            "Performance by Payer",
            ["practice_id", "practice_name", "payers"]
        ),
        (
            f"/api/v1/analytics/practice/{practice_guid}/cpt-performance?days_back=365",
            "Performance by CPT Code",
            ["practice_id", "practice_name", "cpt_codes"]
        ),
        (
            f"/api/v1/analytics/practice/{practice_guid}/high-risk-claims?days_back=365&limit=20",
            "High Risk Claims",
            ["practice_id", "practice_name", "high_risk_claims"]
        ),
    ]
    
    results = {}
    for endpoint, description, expected_keys in endpoints:
        success, data = test_endpoint(base_url, endpoint, description)
        if success:
            valid = validate_response(data, expected_keys, description)
            results[description] = {"success": success, "valid": valid, "data": data}
        else:
            results[description] = {"success": False, "valid": False, "data": None}
    
    # Summary
    print(f"\n{'='*70}")
    print("Test Summary")
    print(f"{'='*70}")
    
    passed = sum(1 for r in results.values() if r["success"] and r["valid"])
    total = len(results)
    
    for description, result in results.items():
        status = "✅ PASS" if (result["success"] and result["valid"]) else "❌ FAIL"
        print(f"{status}: {description}")
    
    print(f"\nResults: {passed}/{total} endpoints passed validation")
    
    if passed == total:
        print("\n🎉 All endpoints are working correctly!")
    else:
        print("\n⚠️  Some endpoints failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())


#!/usr/bin/env python3
"""Test the new practice analytics API endpoints."""

import requests
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint: str, description: str):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Endpoint: {endpoint}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=60)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Success! Status: {response.status_code}")
        print(f"\nResponse (first 500 chars):")
        print(json.dumps(data, indent=2)[:500])
        if len(json.dumps(data, indent=2)) > 500:
            print("\n... (truncated)")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


if __name__ == "__main__":
    # You'll need to replace this with an actual practice GUID from your database
    # For testing, we'll use a placeholder
    practice_guid = "test-practice-guid"  # Replace with actual GUID
    
    print("Testing Practice Analytics API Endpoints")
    print(f"Base URL: {BASE_URL}")
    print(f"Practice GUID: {practice_guid}")
    print("\nNote: Replace 'test-practice-guid' with an actual practice GUID from your database")
    
    # Test endpoints
    endpoints = [
        (f"/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=365", 
         "Performance Summary"),
        (f"/api/v1/analytics/practice/{practice_guid}/action-items?days_back=365", 
         "Prioritized Action Items"),
        (f"/api/v1/analytics/practice/{practice_guid}/payer-performance?days_back=365", 
         "Performance by Payer"),
        (f"/api/v1/analytics/practice/{practice_guid}/cpt-performance?days_back=365", 
         "Performance by CPT Code"),
        (f"/api/v1/analytics/practice/{practice_guid}/high-risk-claims?days_back=365&limit=20", 
         "High Risk Claims"),
    ]
    
    results = {}
    for endpoint, description in endpoints:
        result = test_endpoint(endpoint, description)
        results[description] = result
    
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for description, result in results.items():
        status = "✅ Pass" if result is not None else "❌ Fail"
        print(f"{status}: {description}")


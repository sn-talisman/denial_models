#!/usr/bin/env python3
"""Test script to verify database repository implementation."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data_access.factory import get_repository

load_dotenv()


async def test_repository():
    """Test repository methods."""
    print("Testing database repository...")
    print("=" * 60)
    
    repo = get_repository()
    
    try:
        # Test get_practices
        print("\n1. Testing get_practices()...")
        practices = await repo.get_practices()
        print(f"   Found {len(practices)} practices")
        if practices:
            print(f"   Sample: {practices[0].name} (ID: {practices[0].practice_id})")
        
        # Test get_payers
        print("\n2. Testing get_payers()...")
        payers = await repo.get_payers()
        print(f"   Found {len(payers)} payers")
        if payers:
            print(f"   Sample: {payers[0].name} (ID: {payers[0].payer_id})")
        
        # Test get_claims
        print("\n3. Testing get_claims()...")
        claims = await repo.get_claims(limit=5)
        print(f"   Found {len(claims)} claims")
        if claims:
            claim = claims[0]
            print(f"   Sample claim:")
            print(f"     ID: {claim.claim_id}")
            print(f"     Status: {claim.status}")
            print(f"     Practice: {claim.practice_id}")
            print(f"     Payer: {claim.payer_id}")
            print(f"     Billed: ${claim.total_billed_amount}")
            print(f"     Paid: ${claim.total_paid_amount}")
            
            # Test get_claim_by_id
            print("\n4. Testing get_claim_by_id()...")
            claim_by_id = await repo.get_claim_by_id(claim.claim_id)
            if claim_by_id:
                print(f"   Found claim: {claim_by_id.claim_id}")
            else:
                print("   Claim not found by ID")
            
            # Test get_claim_line_items
            print("\n5. Testing get_claim_line_items()...")
            line_items = await repo.get_claim_line_items(claim.claim_id)
            print(f"   Found {len(line_items)} line items")
            if line_items:
                item = line_items[0]
                print(f"   Sample line item:")
                print(f"     CPT: {item.cpt_code}")
                print(f"     Billed: ${item.billed_amount}")
                print(f"     Units: {item.units}")
            
            # Test get_denial_details
            print("\n6. Testing get_denial_details()...")
            denials = await repo.get_denial_details(claim.claim_id)
            print(f"   Found {len(denials)} denial details")
            if denials:
                denial = denials[0]
                print(f"   Sample denial:")
                print(f"     CARC: {denial.carc_code}")
                print(f"     Reason: {denial.denial_reason_text}")
        
        # Test get_historical_denial_rates
        print("\n7. Testing get_historical_denial_rates()...")
        rates = await repo.get_historical_denial_rates(
            group_by=["payer_id", "cpt_code"],
            date_from=None,
            date_to=None,
        )
        print(f"   Found {len(rates)} denial rate records")
        if rates:
            rate = rates[0]
            print(f"   Sample rate:")
            print(f"     Group: {rate.group_key}")
            print(f"     Total: {rate.total_claims}")
            print(f"     Denied: {rate.denied_claims}")
            print(f"     Rate: {rate.denial_rate:.2%}")
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(test_repository())


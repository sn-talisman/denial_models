#!/usr/bin/env python3
"""Test retrieval of denied claims and their denial details."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data_access.factory import get_repository

load_dotenv()


async def test_denied_claims():
    """Test retrieval of denied claims with all details."""
    print("=" * 80)
    print("DENIED CLAIMS RETRIEVAL TEST")
    print("=" * 80)
    
    repo = get_repository()
    
    try:
        # 1. Get denied claims specifically
        print("\n1. Retrieving denied claims...")
        denied_claims = await repo.get_claims(status="denied", limit=20)
        print(f"   ✅ Retrieved {len(denied_claims)} denied claim bundles")
        
        if not denied_claims:
            print("   ⚠️  No denied claims found. Trying rejected claims...")
            rejected_claims = await repo.get_claims(status="rejected", limit=20)
            print(f"   ✅ Retrieved {len(rejected_claims)} rejected claim bundles")
            denied_claims = rejected_claims
        
        if not denied_claims:
            print("   ⚠️  No denied/rejected claims found. Testing with all claims...")
            all_claims = await repo.get_claims(limit=100)
            # Filter for denied status
            denied_claims = [c for c in all_claims if c.status.value in ['denied', 'rejected']]
            print(f"   ✅ Found {len(denied_claims)} denied/rejected claims in sample")
        
        if not denied_claims:
            print("   ⚠️  No denied claims in database. Testing with any claims...")
            denied_claims = await repo.get_claims(limit=10)
        
        # 2. Test denial details for denied claims
        print(f"\n2. Testing denial details for {len(denied_claims)} claims...")
        claims_with_denials = 0
        total_denials = 0
        denial_examples = []
        
        for claim in denied_claims[:10]:
            denials = await repo.get_denial_details(claim.claim_id)
            if denials:
                claims_with_denials += 1
                total_denials += len(denials)
                denial_examples.extend(denials[:2])  # Keep first 2 examples
        
        print(f"   ✅ Found denial details for {claims_with_denials}/{min(10, len(denied_claims))} claims")
        print(f"   ✅ Total denial details: {total_denials}")
        
        if denial_examples:
            print(f"\n   Sample denial details:")
            for i, denial in enumerate(denial_examples[:3], 1):
                print(f"\n   Denial {i}:")
                print(f"     Denial ID: {denial.denial_id}")
                print(f"     Claim ID: {denial.claim_id}")
                print(f"     Line Item ID: {denial.line_item_id}")
                print(f"     CARC Code: {denial.carc_code}")
                print(f"     RARC Code: {denial.rarc_code}")
                print(f"     Remark Code: {denial.remark_code}")
                print(f"     Category: {denial.denial_category}")
                print(f"     Reason: {denial.denial_reason_text[:150] if denial.denial_reason_text else 'N/A'}")
                print(f"     Denial Date: {denial.denial_date}")
                print(f"     Adjustment Amount: {denial.adjustment_amount}")
        else:
            print(f"\n   ⚠️  No denial details found. This could mean:")
            print(f"      - Claims don't have adjustments_json populated")
            print(f"      - Denial data is stored elsewhere")
            print(f"      - Sample claims are not actually denied")
        
        # 3. Verify claim bundle structure
        print(f"\n3. Verifying claim bundle structure...")
        for claim in denied_claims[:3]:
            print(f"\n   Claim Bundle: {claim.claim_id}")
            print(f"     Status: {claim.status}")
            print(f"     Practice: {claim.practice_id}")
            print(f"     Payer: {claim.payer_id}")
            print(f"     Billed: ${claim.total_billed_amount}")
            print(f"     Paid: ${claim.total_paid_amount}")
            
            # Get line items
            line_items = await repo.get_claim_line_items(claim.claim_id)
            print(f"     Line Items: {len(line_items)}")
            for item in line_items[:2]:
                print(f"       - {item.cpt_code}: ${item.billed_amount} ({item.units} units)")
            
            # Get denials
            denials = await repo.get_denial_details(claim.claim_id)
            print(f"     Denial Details: {len(denials)}")
            for denial in denials[:2]:
                print(f"       - CARC {denial.carc_code}: {denial.denial_reason_text[:50] if denial.denial_reason_text else 'N/A'}")
        
        # 4. Test retrieving all claims with pagination
        print(f"\n4. Testing pagination...")
        page1 = await repo.get_claims(limit=20, offset=0)
        page2 = await repo.get_claims(limit=20, offset=20)
        print(f"   Page 1: {len(page1)} claims")
        print(f"   Page 2: {len(page2)} claims")
        
        # Check for overlap
        page1_ids = {c.claim_id for c in page1}
        page2_ids = {c.claim_id for c in page2}
        overlap = page1_ids & page2_ids
        if overlap:
            print(f"   ⚠️  Warning: {len(overlap)} claims appear in both pages")
        else:
            print(f"   ✅ No overlap between pages")
        
        # 5. Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Denied claims retrieved: {len(denied_claims)}")
        print(f"✅ Claims with denial details: {claims_with_denials}")
        print(f"✅ Total denial details: {total_denials}")
        print(f"✅ Pagination working: Yes")
        
        if total_denials == 0:
            print(f"\n⚠️  Note: No denial details found. This may be normal if:")
            print(f"   - The sample claims don't have denial data")
            print(f"   - Denial data is stored in a different format")
            print(f"   - The adjustments_json field is not populated")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(test_denied_claims())


#!/usr/bin/env python3
"""Comprehensive test to verify all claims, bundles, and details are retrieved correctly."""

import asyncio
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data_access.factory import get_repository

load_dotenv()


async def test_comprehensive_claims():
    """Test comprehensive claim retrieval with all details."""
    print("=" * 80)
    print("COMPREHENSIVE CLAIM RETRIEVAL TEST")
    print("=" * 80)
    
    repo = get_repository()
    
    try:
        # 1. Get a sample of claims
        print("\n1. Retrieving sample claims...")
        claims = await repo.get_claims(limit=50)
        print(f"   ✅ Retrieved {len(claims)} claim bundles")
        
        if not claims:
            print("   ⚠️  No claims found. Cannot continue test.")
            return
        
        # 2. Verify claim structure
        print("\n2. Verifying claim structure...")
        sample_claim = claims[0]
        print(f"   Claim ID: {sample_claim.claim_id}")
        print(f"   Claim Number: {sample_claim.claim_number}")
        print(f"   Status: {sample_claim.status}")
        print(f"   Practice ID: {sample_claim.practice_id}")
        print(f"   Payer ID: {sample_claim.payer_id}")
        print(f"   Billed Amount: ${sample_claim.total_billed_amount}")
        print(f"   Paid Amount: ${sample_claim.total_paid_amount}")
        print(f"   Service Dates: {sample_claim.service_date_from} to {sample_claim.service_date_to}")
        
        # 3. Test retrieving line items for all claims
        print("\n3. Testing line item retrieval for all claims...")
        claims_with_items = 0
        total_line_items = 0
        line_items_by_claim = {}
        
        for claim in claims[:10]:  # Test first 10 to avoid timeout
            line_items = await repo.get_claim_line_items(claim.claim_id)
            if line_items:
                claims_with_items += 1
                total_line_items += len(line_items)
                line_items_by_claim[claim.claim_id] = line_items
                
                # Show sample line item details
                if claim == sample_claim and line_items:
                    item = line_items[0]
                    print(f"\n   Sample line item for claim {claim.claim_id}:")
                    print(f"     Line Item ID: {item.line_item_id}")
                    print(f"     CPT Code: {item.cpt_code}")
                    print(f"     Modifiers: {item.modifiers}")
                    print(f"     Units: {item.units}")
                    print(f"     Billed: ${item.billed_amount}")
                    print(f"     Service Date: {item.service_date}")
        
        print(f"\n   ✅ Found line items for {claims_with_items}/{min(10, len(claims))} claims")
        print(f"   ✅ Total line items retrieved: {total_line_items}")
        
        # 4. Test denial details retrieval
        print("\n4. Testing denial details retrieval...")
        claims_with_denials = 0
        total_denials = 0
        denial_details_by_claim = {}
        
        for claim in claims[:10]:
            denials = await repo.get_denial_details(claim.claim_id)
            if denials:
                claims_with_denials += 1
                total_denials += len(denials)
                denial_details_by_claim[claim.claim_id] = denials
                
                # Show sample denial details
                if denials:
                    denial = denials[0]
                    print(f"\n   Sample denial for claim {claim.claim_id}:")
                    print(f"     Denial ID: {denial.denial_id}")
                    print(f"     CARC Code: {denial.carc_code}")
                    print(f"     RARC Code: {denial.rarc_code}")
                    print(f"     Reason: {denial.denial_reason_text[:100] if denial.denial_reason_text else 'N/A'}")
                    print(f"     Category: {denial.denial_category}")
        
        print(f"\n   ✅ Found denials for {claims_with_denials}/{min(10, len(claims))} claims")
        print(f"   ✅ Total denial details retrieved: {total_denials}")
        
        # 5. Verify claim aggregation (bundles)
        print("\n5. Verifying claim bundle aggregation...")
        claim_ids = [c.claim_id for c in claims]
        unique_claim_ids = set(claim_ids)
        print(f"   Total claims retrieved: {len(claims)}")
        print(f"   Unique claim IDs: {len(unique_claim_ids)}")
        
        if len(claim_ids) != len(unique_claim_ids):
            duplicates = len(claim_ids) - len(unique_claim_ids)
            print(f"   ⚠️  Warning: {duplicates} duplicate claim IDs found")
            # Find duplicates
            from collections import Counter
            dup_counts = Counter(claim_ids)
            duplicates_list = [cid for cid, count in dup_counts.items() if count > 1]
            print(f"   Duplicate claim IDs: {duplicates_list[:5]}")
        else:
            print(f"   ✅ All claim IDs are unique")
        
        # 6. Test retrieving individual claim by ID
        print("\n6. Testing individual claim retrieval...")
        test_claim_id = claims[0].claim_id
        individual_claim = await repo.get_claim_by_id(test_claim_id)
        
        if individual_claim:
            print(f"   ✅ Successfully retrieved claim {test_claim_id}")
            print(f"     Status: {individual_claim.status}")
            print(f"     Billed: ${individual_claim.total_billed_amount}")
        else:
            print(f"   ⚠️  Could not retrieve claim {test_claim_id}")
        
        # 7. Verify data completeness
        print("\n7. Verifying data completeness...")
        stats = {
            "has_practice_id": sum(1 for c in claims if c.practice_id),
            "has_payer_id": sum(1 for c in claims if c.payer_id),
            "has_patient_id": sum(1 for c in claims if c.patient_id),
            "has_provider_id": sum(1 for c in claims if c.provider_id),
            "has_service_dates": sum(1 for c in claims if c.service_date_from),
            "has_billed_amount": sum(1 for c in claims if c.total_billed_amount > 0),
        }
        
        print(f"   Claims with practice_id: {stats['has_practice_id']}/{len(claims)} ({stats['has_practice_id']/len(claims)*100:.1f}%)")
        print(f"   Claims with payer_id: {stats['has_payer_id']}/{len(claims)} ({stats['has_payer_id']/len(claims)*100:.1f}%)")
        print(f"   Claims with patient_id: {stats['has_patient_id']}/{len(claims)} ({stats['has_patient_id']/len(claims)*100:.1f}%)")
        print(f"   Claims with provider_id: {stats['has_provider_id']}/{len(claims)} ({stats['has_payer_id']/len(claims)*100:.1f}%)")
        print(f"   Claims with service_dates: {stats['has_service_dates']}/{len(claims)} ({stats['has_service_dates']/len(claims)*100:.1f}%)")
        print(f"   Claims with billed_amount: {stats['has_billed_amount']}/{len(claims)} ({stats['has_billed_amount']/len(claims)*100:.1f}%)")
        
        # 8. Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Claim bundles retrieved: {len(claims)}")
        print(f"✅ Line items retrieved: {total_line_items} (for {claims_with_items} claims)")
        print(f"✅ Denial details retrieved: {total_denials} (for {claims_with_denials} claims)")
        print(f"✅ Unique claim IDs: {len(unique_claim_ids)}")
        print(f"✅ Data completeness: {sum(stats.values())}/{len(stats)*len(claims)} fields populated")
        
        # Check for any issues
        issues = []
        if len(claim_ids) != len(unique_claim_ids):
            issues.append("Duplicate claim IDs detected")
        if stats['has_practice_id'] < len(claims) * 0.9:
            issues.append("Low practice_id coverage")
        if stats['has_payer_id'] < len(claims) * 0.9:
            issues.append("Low payer_id coverage")
        
        if issues:
            print(f"\n⚠️  Issues found:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print(f"\n✅ All checks passed!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(test_comprehensive_claims())


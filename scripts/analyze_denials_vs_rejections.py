#!/usr/bin/env python3
"""Analyze the distinction between denials and rejections in the data."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data_access.factory import get_repository
from src.utils.logging_config import configure_logging
from datetime import date, timedelta
import os

load_dotenv()
configure_logging()


async def analyze():
    """Analyze denials vs rejections in the database."""
    repo = get_repository()
    try:
        print("🔍 Analyzing Denials vs Rejections\n")
        
        # Get claims with different statuses
        print("1. Checking claim status distribution...")
        all_claims = await repo.get_claims(
            date_from=date.today() - timedelta(days=365),
            limit=1000,
        )
        
        status_counts = {}
        denied_claims = []
        rejected_claims = []
        
        for claim in all_claims:
            status = claim.status.value if claim.status else "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if claim.status and claim.status.value == "denied":
                denied_claims.append(claim)
            elif claim.status and claim.status.value == "rejected":
                rejected_claims.append(claim)
        
        print(f"   Total claims analyzed: {len(all_claims)}")
        print(f"   Status distribution:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"      {status}: {count}")
        
        print(f"\n   Claims with DENIED status: {len(denied_claims)}")
        print(f"   Claims with REJECTED status: {len(rejected_claims)}")
        
        # Check denial details for denied claims
        print(f"\n2. Analyzing denial details for DENIED claims...")
        denied_with_details = 0
        denied_carc_codes = set()
        
        for claim in denied_claims[:50]:  # Sample
            details = await repo.get_denial_details(claim.claim_id)
            if details:
                denied_with_details += 1
                for detail in details:
                    if detail.carc_code:
                        denied_carc_codes.add(detail.carc_code)
        
        print(f"   Denied claims with denial details: {denied_with_details}/{min(50, len(denied_claims))}")
        print(f"   Unique CARC codes in denied claims: {sorted(denied_carc_codes)}")
        
        # Check denial details for rejected claims
        print(f"\n3. Analyzing denial details for REJECTED claims...")
        rejected_with_details = 0
        rejected_carc_codes = set()
        
        for claim in rejected_claims[:50]:  # Sample
            details = await repo.get_denial_details(claim.claim_id)
            if details:
                rejected_with_details += 1
                for detail in details:
                    if detail.carc_code:
                        rejected_carc_codes.add(detail.carc_code)
        
        print(f"   Rejected claims with denial details: {rejected_with_details}/{min(50, len(rejected_claims))}")
        print(f"   Unique CARC codes in rejected claims: {sorted(rejected_carc_codes)}")
        
        # Check database status fields directly
        print(f"\n4. Checking raw database status fields...")
        from sqlalchemy import text
        async with repo.session_factory() as session:
            query = text("""
                SELECT 
                    claim_status,
                    payer_status,
                    COUNT(*) as count,
                    COUNT(CASE WHEN adjustments_json IS NOT NULL OR adjustment_descriptions IS NOT NULL THEN 1 END) as with_adjustments
                FROM tebra.fin_claim_line
                WHERE date_of_service >= :date_from
                GROUP BY claim_status, payer_status
                ORDER BY count DESC
                LIMIT 20
            """)
            result = await session.execute(query, {"date_from": date.today() - timedelta(days=365)})
            rows = result.fetchall()
            
            print(f"   Top status combinations:")
            for row in rows:
                print(f"      claim_status='{row.claim_status}', payer_status='{row.payer_status}': {row.count} claims ({row.with_adjustments} with adjustments)")
        
        # Summary and recommendations
        print(f"\n📊 Summary:")
        print(f"   - DENIED: {len(denied_claims)} claims")
        print(f"   - REJECTED: {len(rejected_claims)} claims")
        print(f"   - Both have denial details (adjustments_json/adjustment_descriptions)")
        
        print(f"\n💡 Recommendation:")
        if len(denied_claims) > 0 and len(rejected_claims) > 0:
            print(f"   Both denials and rejections exist. For ML prediction:")
            print(f"   - Option 1: Combine both as 'is_denied=True' (current approach)")
            print(f"   - Option 2: Separate models for denials vs rejections")
            print(f"   - Option 3: Add 'is_rejected' feature in addition to 'is_denied'")
        elif len(denied_claims) > 0:
            print(f"   Only DENIED claims found. Current approach is correct.")
        elif len(rejected_claims) > 0:
            print(f"   Only REJECTED claims found. Should update 'is_denied' to include rejections.")
        else:
            print(f"   ⚠️  No denied or rejected claims found in status fields.")
            print(f"   Need to check denial details (adjustments) to identify denials.")
        
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(analyze())


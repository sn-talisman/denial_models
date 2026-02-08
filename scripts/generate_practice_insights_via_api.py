#!/usr/bin/env python3
"""Generate practice insights markdown file using HTTP API endpoints."""

import requests
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
TIMEOUT = 300  # 5 minutes for analysis


def get_practices_with_claims(days_back: int = 365) -> List[Dict[str, str]]:
    """Get list of practices that have claims using the analytics API."""
    print(f"\n📋 Fetching practices with claims (days_back={days_back})...")
    url = f"{BASE_URL}/api/v1/analytics/practices?days_back={days_back}&min_claims=1"
    print(f"   URL: {url}")
    
    try:
        print(f"   ⏳ Sending request...")
        response = requests.get(url, timeout=60)
        print(f"   ✅ Received response: {response.status_code}")
        response.raise_for_status()
        practices_data = response.json()
        print(f"   ✅ Parsed {len(practices_data)} practices")
        
        practices = [
            {
                "practice_id": p["practice_id"],
                "practice_name": p["practice_name"]
            }
            for p in practices_data
        ]
        print(f"   ✅ Returning {len(practices)} practices")
        return practices
    except Exception as e:
        print(f"⚠️  Error getting practices from API: {e}")
        print("   Falling back to direct database query...")
        import traceback
        traceback.print_exc()
        
        # Fallback: use database directly with proper async handling
        async def _get_practices():
            repository = get_repository()
            try:
                date_to = date.today()
                date_from = date_to - timedelta(days=days_back)
                
                practices = await repository.get_practices()
                practices_with_claims = []
                
                for practice in practices[:20]:  # Limit to first 20 for performance
                    claims = await repository.get_claims(
                        practice_id=practice.practice_id,
                        date_from=date_from,
                        date_to=date_to,
                        limit=1
                    )
                    if claims:
                        practices_with_claims.append({
                            "practice_id": practice.practice_id,
                            "practice_name": practice.name
                        })
                
                return practices_with_claims
            finally:
                await repository.close()
        
        return asyncio.run(_get_practices())


def call_api_endpoint(endpoint: str, description: str) -> Optional[Dict[str, Any]]:
    """Call an API endpoint and return the JSON response."""
    url = f"{BASE_URL}{endpoint}"
    print(f"  📡 Calling: {description}...")
    print(f"     URL: {url}")
    
    try:
        print(f"     ⏳ Sending request...")
        response = requests.get(url, timeout=TIMEOUT)
        print(f"     ✅ Received response: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"     ✅ Parsed JSON response")
        return data
    except requests.exceptions.Timeout:
        print(f"    ❌ Timeout after {TIMEOUT} seconds")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"    ❌ HTTP Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"    Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_markdown_for_practice(
    practice_id: str,
    practice_name: str,
    days_back: int = 365,
    practice_num: int = 0,
    total_practices: int = 0,
    performance_summary: Optional[Dict[str, Any]] = None
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Generate markdown content for a single practice using API endpoints.
    
    Returns:
        Tuple of (markdown_content, performance_summary) - returns performance_summary for reuse
    """
    
    print(f"\n{'='*70}")
    print(f"📊 Processing Practice {practice_num}/{total_practices}: {practice_name}")
    print(f"   Practice ID: {practice_id}")
    print(f"   Days Back: {days_back}")
    print(f"{'='*70}")
    
    # Call all endpoints
    if not performance_summary:
        print(f"\n[1/5] Fetching performance summary...")
        performance_summary = call_api_endpoint(
            f"/api/v1/analytics/practice/{practice_id}/performance-summary?days_back={days_back}",
            "Performance Summary"
        )
    else:
        print(f"\n[1/5] Using cached performance summary...")
        print(f"   ✅ Performance summary already available")
    
    print(f"\n[2/5] Fetching prioritized action items...")
    action_items = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/action-items?days_back={days_back}",
        "Action Items"
    )
    
    print(f"\n[3/5] Fetching payer performance...")
    payer_performance = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/payer-performance?days_back={days_back}",
        "Payer Performance"
    )
    
    print(f"\n[4/5] Fetching CPT code performance...")
    cpt_performance = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/cpt-performance?days_back={days_back}",
        "CPT Performance"
    )
    
    print(f"\n[5/6] Fetching high-risk claims...")
    high_risk_claims = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/high-risk-claims?days_back={days_back}&limit=20",
        "High Risk Claims"
    )
    
    print(f"\n[6/7] Fetching CARC/RARC denial reasons...")
    denial_reasons = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/denial-reasons?days_back={days_back}",
        "Denial Reasons (CARC/RARC)"
    )
    
    print(f"\n[7/8] Fetching CPT-CARC correlation...")
    cpt_carc_correlation = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/cpt-carc-correlation?days_back={days_back}",
        "CPT-CARC Correlation"
    )
    
    print(f"\n[8/8] Fetching rejection patterns...")
    rejection_patterns = call_api_endpoint(
        f"/api/v1/analytics/practice/{practice_id}/rejection-patterns?days_back={days_back}",
        "Rejection Patterns"
    )
    
    if not performance_summary:
        print(f"  ⚠️  Skipping {practice_name} - no data available")
        return "", None
    
    print(f"\n✅ All endpoints completed for {practice_name}")
    print(f"   Generating markdown...")
    
    # Generate markdown
    md = []
    md.append(f"## {practice_name}")
    md.append("")
    
    # Performance Summary
    md.append("### 📊 Performance Summary")
    md.append("")
    md.append("| Metric | Value | vs Overall |")
    md.append("|--------|-------|------------|")
    md.append(f"| Total Claims | {performance_summary['total_claims']:,} | - |")
    
    denial_rate = performance_summary['denial_rate']
    denial_rate_vs = performance_summary['denial_rate_vs_overall']
    md.append(f"| Denial Rate | {denial_rate:.1%} | {'🔴 +' if denial_rate_vs > 0 else '🟢 '}{denial_rate_vs:+.1%} |")
    
    md.append(f"| Total Billed | ${performance_summary['total_billed']:,.2f} | - |")
    md.append(f"| Total Paid | ${performance_summary['total_paid']:,.2f} | - |")
    md.append(f"| **Denied Amount** | **${performance_summary['denied_amount']:,.2f}** | **Potential Recovery** |")
    
    avg_prob = performance_summary['avg_denial_probability']
    avg_prob_vs = performance_summary['avg_probability_vs_overall']
    md.append(f"| Avg Denial Probability | {avg_prob:.3f} | {'🔴 +' if avg_prob_vs > 0 else '🟢 '}{avg_prob_vs:+.3f} |")
    md.append(f"| High Risk Claims | {performance_summary['high_risk_claims']} ({performance_summary['high_risk_pct']:.1%}) | - |")
    md.append("")
    
    # Prioritized Action Items
    if action_items and action_items.get('action_items'):
        md.append("### 🎯 Prioritized Action Items")
        md.append("")
        
        for idx, item in enumerate(action_items['action_items'][:10], 1):
            md.append(f"#### {idx}. {item['title']}")
            md.append("")
            md.append(f"**Financial Impact**: ${item['financial_impact']:,.2f} in denied claims")
            md.append("")
            md.append(f"**Recommendation**: {item['recommendation']}")
            if item.get('details'):
                md.append("")
                md.append(f"*{item['details']}*")
            md.append("")
    else:
        md.append("### 🎯 Prioritized Action Items")
        md.append("")
        md.append("*No specific action items identified. Practice performance is within normal parameters.*")
        md.append("")
    
    # Performance by Payer
    if payer_performance and payer_performance.get('payers'):
        md.append("### 📋 Detailed Analysis")
        md.append("")
        md.append("#### Performance by Payer")
        md.append("")
        md.append("| Payer | Claims | Denial Rate | Denied Amount | Avg Risk |")
        md.append("|-------|--------|-------------|---------------|----------|")
        
        for payer in payer_performance['payers'][:10]:
            payer_name = payer['payer_name'][:40]
            md.append(f"| {payer_name} | {payer['total_claims']} | {payer['denial_rate']:.1%} | ${payer['denied_amount']:,.2f} | {payer['avg_denial_probability']:.2f} |")
        md.append("")
    
    # Performance by CPT Code
    if cpt_performance and cpt_performance.get('cpt_codes'):
        md.append("#### Performance by CPT Code")
        md.append("")
        md.append("| CPT Code | Claims | Denial Rate | Denied Amount | Avg Risk |")
        md.append("|----------|--------|-------------|---------------|----------|")
        
        for cpt in cpt_performance['cpt_codes'][:10]:
            md.append(f"| {cpt['cpt_code']} | {cpt['total_claims']} | {cpt['denial_rate']:.1%} | ${cpt['denied_amount']:,.2f} | {cpt['avg_denial_probability']:.2f} |")
        md.append("")
    
    # High Risk Claims
    if high_risk_claims and high_risk_claims.get('high_risk_claims'):
        md.append("#### High-Risk Claims Requiring Immediate Attention")
        md.append("")
        md.append("| Claim ID | Payer | CPT | Denial Prob | Billed Amount |")
        md.append("|----------|-------|-----|-------------|---------------|")
        
        for claim in high_risk_claims['high_risk_claims'][:20]:
            claim_id = claim['claim_id'][:8] if claim.get('claim_id') else 'N/A'
            payer_name = claim['payer_name'][:25] if claim.get('payer_name') else 'Unknown'
            cpt_code = claim['cpt_code'][:10] if claim.get('cpt_code') else 'N/A'
            md.append(f"| {claim_id} | {payer_name} | {cpt_code} | {claim['denial_probability']:.1%} | ${claim['billed_amount']:,.2f} |")
        md.append("")
    else:
        md.append("#### High-Risk Claims Requiring Immediate Attention")
        md.append("")
        md.append("*No high-risk claims identified.*")
        md.append("")
    
    # CARC/RARC Analysis
    if denial_reasons:
        md.append("#### Denial Reasons (CARC/RARC Codes)")
        md.append("")
        
        # CARC Codes
        if denial_reasons.get('carc_codes'):
            md.append("##### Top CARC (Claim Adjustment Reason) Codes")
            md.append("")
            md.append("| CARC Code | Description | Occurrences | Affected Claims | Total Amount |")
            md.append("|-----------|-------------|-------------|-----------------|--------------|")
            
            for carc in denial_reasons['carc_codes'][:15]:
                desc = carc['description'][:50] if carc.get('description') else f"CARC {carc['carc_code']}"
                md.append(f"| {carc['carc_code']} | {desc} | {carc['occurrence_count']} | {carc['affected_claims']} | ${carc['total_adjustment_amount']:,.2f} |")
            md.append("")
        
        # RARC Codes
        if denial_reasons.get('rarc_codes'):
            md.append("##### Top RARC (Remittance Advice Remark) Codes")
            md.append("")
            md.append("| RARC Code | Occurrences | Affected Claims | Total Amount |")
            md.append("|----------|-------------|-----------------|--------------|")
            
            for rarc in denial_reasons['rarc_codes'][:15]:
                md.append(f"| {rarc['rarc_code']} | {rarc['occurrence_count']} | {rarc['affected_claims']} | ${rarc['total_adjustment_amount']:,.2f} |")
            md.append("")
        
        if not denial_reasons.get('carc_codes') and not denial_reasons.get('rarc_codes'):
            md.append("*No CARC/RARC codes found in denial details.*")
            md.append("")
    
    # CPT-CARC Correlation Analysis
    if cpt_carc_correlation and cpt_carc_correlation.get('cpt_carc'):
        md.append("#### CPT-CARC Correlation Analysis")
        md.append("")
        md.append("This analysis shows which procedure codes are most commonly associated with which denial reason codes.")
        md.append("")
        md.append("##### Top CPT-CARC Combinations")
        md.append("")
        md.append("| CPT Code | CARC Code | Description | Occurrences | Affected Claims | Total Amount |")
        md.append("|----------|-----------|-------------|-------------|-----------------|--------------|")
        
        for combo in cpt_carc_correlation['cpt_carc'][:15]:
            desc = combo['carc_description'][:40] if combo.get('carc_description') else f"CARC {combo['carc_code']}"
            md.append(f"| {combo['cpt_code']} | {combo['carc_code']} | {desc} | {combo['occurrence_count']} | {combo['affected_claims']} | ${combo['total_adjustment_amount']:,.2f} |")
        md.append("")
    
    # Rejection Pattern Analysis
    if rejection_patterns:
        md.append("#### Rejection Pattern Analysis")
        md.append("")
        md.append("This analysis identifies which CPT codes are associated with rejection issues (missing fields, invalid data).")
        md.append("")
        
        if rejection_patterns.get('rejection_patterns') and len(rejection_patterns['rejection_patterns']) > 0:
            md.append("##### CPT Codes with Rejection Issues")
            md.append("")
            md.append("| CPT Code | Rejections | Rejection Rate | Missing Submitted Date | Missing Patient ID | Missing Provider ID | Missing Service Date | Risk Score |")
            md.append("|----------|------------|----------------|----------------------|-------------------|---------------------|---------------------|------------|")
            
            for pattern in rejection_patterns['rejection_patterns'][:15]:
                if pattern['total_rejections'] > 0:
                    md.append(f"| {pattern['cpt_code']} | {pattern['total_rejections']} | {pattern['rejection_rate']:.1%} | {pattern.get('missing_submitted_date', 0)} | {pattern['missing_patient_id']} | {pattern['missing_provider_id']} | {pattern['missing_service_date']} | {pattern['rejection_risk_score']} |")
            md.append("")
            
            # Add actionable insights for top rejection patterns
            top_rejection = rejection_patterns['rejection_patterns'][0] if rejection_patterns['rejection_patterns'] else None
            if top_rejection and top_rejection['total_rejections'] > 0:
                md.append("##### Key Rejection Insights")
                md.append("")
                issues = []
                if top_rejection.get('missing_submitted_date', 0) > 0:
                    issues.append(f"**Missing Submitted Date** ({top_rejection['missing_submitted_date']} occurrences) - Claims cannot be processed without a submission date")
                if top_rejection.get('missing_line_items', 0) > 0:
                    issues.append(f"**Missing Line Items** ({top_rejection['missing_line_items']} occurrences) - Claims must have at least one line item")
                if top_rejection['missing_patient_id'] > 0:
                    issues.append(f"Missing Patient ID ({top_rejection['missing_patient_id']} occurrences)")
                if top_rejection['missing_provider_id'] > 0:
                    issues.append(f"Missing Provider ID ({top_rejection['missing_provider_id']} occurrences)")
                if top_rejection['missing_service_date'] > 0:
                    issues.append(f"Missing Service Date ({top_rejection['missing_service_date']} occurrences)")
                if top_rejection['invalid_date_order'] > 0:
                    issues.append(f"Invalid Date Order ({top_rejection['invalid_date_order']} occurrences) - Submitted date before service date")
                if top_rejection.get('missing_cpt_in_line_items', 0) > 0:
                    issues.append(f"Missing CPT Codes in Line Items ({top_rejection['missing_cpt_in_line_items']} occurrences)")
                
                if issues:
                    md.append(f"**CPT {top_rejection['cpt_code']}** has the highest rejection risk ({top_rejection['rejection_rate']:.1%} rejection rate). Common issues:")
                    for issue in issues:
                        md.append(f"- {issue}")
                    md.append("")
                else:
                    md.append(f"**CPT {top_rejection['cpt_code']}** has {top_rejection['total_rejections']} rejection(s) but no specific field issues detected. Review claim submission process.")
                    md.append("")
        else:
            md.append("*No rejected claims found in the analysis period. All claims were either paid or denied (not rejected).*")
            md.append("")
    
    md.append("")
    md.append("---")
    md.append("")
    
    markdown_content = "\n".join(md)
    print(f"   ✅ Markdown generated ({len(markdown_content)} characters)")
    
    return markdown_content, performance_summary


def main():
    """Main function to generate practice insights via API."""
    print("🚀 Generating Practice Insights via HTTP API")
    print("="*70)
    print(f"API Base URL: {BASE_URL}")
    
    # Get parameters from environment
    days_back = int(os.getenv("DAYS_BACK", "365"))
    practice_filter = os.getenv("PRACTICE_FILTER", "").strip()
    
    print(f"Days Back: {days_back}")
    if practice_filter:
        print(f"Practice Filter: {practice_filter}")
    
    # Check if API is available
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        print("✅ API server is available")
    except Exception as e:
        print(f"❌ API server is not available at {BASE_URL}")
        print(f"   Error: {e}")
        print(f"\n   Please start the server with:")
        print(f"   uvicorn src.api.app:app --host 0.0.0.0 --port 8001")
        return
    
    # Get practices with claims
    print(f"\n📋 Getting practices with claims (last {days_back} days)...")
    practices = get_practices_with_claims(days_back=days_back)
    
    if not practices:
        print("❌ No practices with claims found")
        return
    
    print(f"✅ Found {len(practices)} practices with claims")
    
    # Filter by practice name if specified
    if practice_filter:
        original_count = len(practices)
        practices = [
            p for p in practices 
            if practice_filter.upper() in p['practice_name'].upper()
        ]
        if not practices:
            print(f"❌ No practices found matching filter: {practice_filter}")
            return
        print(f"✅ Filtered to {len(practices)} practice(s) matching '{practice_filter}'")
    
    # Limit to max practices if specified
    max_practices = int(os.getenv("MAX_PRACTICES", "0"))
    if max_practices > 0 and len(practices) > max_practices:
        print(f"⚠️  Limiting to {max_practices} practice(s) for testing")
        practices = practices[:max_practices]
    
    # Generate markdown for each practice
    print(f"\n{'='*70}")
    print(f"📝 Generating markdown for {len(practices)} practices")
    print(f"{'='*70}")
    
    md_content = []
    md_content.append("# Practice Performance Insights & Actionable Recommendations")
    md_content.append("")
    md_content.append(f"*Generated via HTTP API from {len(practices)} practices*")
    md_content.append("")
    md_content.append("---")
    md_content.append("")
    
    total_claims = 0
    successful_practices = 0
    failed_practices = 0
    practice_claims_map = {}  # Store claims count for each practice
    
    for idx, practice in enumerate(practices, 1):
        print(f"\n{'─'*70}")
        print(f"Practice {idx}/{len(practices)}")
        print(f"{'─'*70}")
        
        try:
            # First get performance summary to get claims count
            print(f"\n[0/5] Fetching performance summary (for claims count)...")
            perf_summary = call_api_endpoint(
                f"/api/v1/analytics/practice/{practice['practice_id']}/performance-summary?days_back={days_back}",
                "Performance Summary"
            )
            
            if perf_summary:
                claims_count = perf_summary.get('total_claims', 0)
                practice_claims_map[practice['practice_id']] = claims_count
                total_claims += claims_count
                print(f"   ✅ Claims count: {claims_count}")
            
            # Now generate full markdown (reuse the performance summary we already fetched)
            practice_md, _ = generate_markdown_for_practice(
                practice['practice_id'],
                practice['practice_name'],
                days_back=days_back,
                practice_num=idx,
                total_practices=len(practices),
                performance_summary=perf_summary  # Reuse the already-fetched summary
            )
            if practice_md:
                md_content.append(practice_md)
                successful_practices += 1
                print(f"   ✅ Successfully processed {practice['practice_name']}")
            else:
                failed_practices += 1
                print(f"   ⚠️  No data for {practice['practice_name']}")
        except Exception as e:
            failed_practices += 1
            print(f"   ❌ Error processing {practice['practice_name']}: {e}")
            import traceback
            traceback.print_exc()
        
        # Progress update
        if idx < len(practices):
            remaining = len(practices) - idx
            elapsed_pct = (idx / len(practices)) * 100
            print(f"\n   📊 Progress: {idx}/{len(practices)} complete ({elapsed_pct:.1f}%), {remaining} remaining")
            print(f"   📈 Total claims so far: {total_claims:,}")
    
    # Update header with total claims and date range
    days_back = int(os.getenv("DAYS_BACK", "365"))
    md_content[2] = f"*Generated via HTTP API from {len(practices)} practice(s) over the past {days_back} days ({total_claims:,} total claims)*"
    
    # Write to file
    print(f"\n{'='*70}")
    print(f"💾 Writing markdown file...")
    print(f"{'='*70}")
    
    output_file = Path("PRACTICE_INSIGHTS.md")
    full_content = "\n".join(md_content)
    output_file.write_text(full_content)
    
    file_size = output_file.stat().st_size
    print(f"   ✅ File written: {output_file}")
    print(f"   File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    
    print(f"\n{'='*70}")
    print(f"✅ Generation Complete!")
    print(f"{'='*70}")
    print(f"   Practices processed: {successful_practices}/{len(practices)}")
    print(f"   Failed: {failed_practices}")
    print(f"   Total Claims: {total_claims:,}")
    print(f"   Output file: {output_file}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()


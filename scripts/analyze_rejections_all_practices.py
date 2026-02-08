#!/usr/bin/env python3
"""Analyze rejection patterns across all practices to ensure comprehensive capture."""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
import requests
import json

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
DAYS_BACK = int(os.getenv("DAYS_BACK", "365"))


def get_all_practices() -> list:
    """Get all practices from the API."""
    url = f"{BASE_URL}/api/v1/analytics/practices?days_back={DAYS_BACK}&min_claims=1"
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting practices: {e}")
        return []


def analyze_rejection_patterns(practice_id: str, practice_name: str, days_back: int) -> dict:
    """Analyze rejection patterns for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/rejection-patterns?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error analyzing {practice_name}: {e}")
        return None


def main():
    print("=" * 80)
    print("Rejection Pattern Analysis - All Practices")
    print("=" * 80)
    print(f"Days Back: {DAYS_BACK}")
    print(f"API Base URL: {BASE_URL}")
    print()
    
    # Get all practices
    practices = get_all_practices()
    print(f"Found {len(practices)} practices with claims")
    print()
    
    # Analyze each practice
    all_rejection_patterns = []
    practices_with_rejections = 0
    total_rejections = 0
    
    # Aggregate rejection issues across all practices
    issue_summary = defaultdict(int)
    cpt_rejection_summary = defaultdict(lambda: {'count': 0, 'practices': set()})
    
    for idx, practice in enumerate(practices, 1):
        practice_id = practice['practice_id']
        practice_name = practice['practice_name']
        
        print(f"[{idx}/{len(practices)}] Analyzing {practice_name}...")
        
        result = analyze_rejection_patterns(practice_id, practice_name, DAYS_BACK)
        
        if result and result.get('rejection_patterns'):
            patterns = result['rejection_patterns']
            practices_with_rejections += 1
            
            for pattern in patterns:
                if pattern['total_rejections'] > 0:
                    total_rejections += pattern['total_rejections']
                    cpt_rejection_summary[pattern['cpt_code']]['count'] += pattern['total_rejections']
                    cpt_rejection_summary[pattern['cpt_code']]['practices'].add(practice_name)
                    
                    # Aggregate issues
                    issue_summary['missing_submitted_date'] += pattern.get('missing_submitted_date', 0)
                    issue_summary['missing_patient_id'] += pattern.get('missing_patient_id', 0)
                    issue_summary['missing_provider_id'] += pattern.get('missing_provider_id', 0)
                    issue_summary['missing_service_date'] += pattern.get('missing_service_date', 0)
                    issue_summary['missing_line_items'] += pattern.get('missing_line_items', 0)
                    issue_summary['invalid_date_order'] += pattern.get('invalid_date_order', 0)
                    issue_summary['missing_cpt_in_line_items'] += pattern.get('missing_cpt_in_line_items', 0)
                    issue_summary['invalid_cpt_count'] += pattern.get('invalid_cpt_count', 0)
                    issue_summary['missing_billed_amount'] += pattern.get('missing_billed_amount', 0)
                    
                    all_rejection_patterns.append({
                        'practice_name': practice_name,
                        'practice_id': practice_id,
                        **pattern
                    })
            
            print(f"  ✅ Found {sum(p['total_rejections'] for p in patterns)} rejection(s)")
        else:
            print(f"  ℹ️  No rejections found")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Practices Analyzed: {len(practices)}")
    print(f"Practices with Rejections: {practices_with_rejections}")
    print(f"Total Rejections: {total_rejections}")
    print()
    
    if issue_summary:
        print("Rejection Issues Summary (across all practices):")
        print("-" * 80)
        for issue, count in sorted(issue_summary.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  {issue.replace('_', ' ').title()}: {count}")
        print()
    
    if cpt_rejection_summary:
        print("Top CPT Codes with Rejections:")
        print("-" * 80)
        sorted_cpts = sorted(cpt_rejection_summary.items(), key=lambda x: x[1]['count'], reverse=True)
        for cpt_code, data in sorted_cpts[:10]:
            practices_list = ', '.join(list(data['practices'])[:3])
            if len(data['practices']) > 3:
                practices_list += f" (+{len(data['practices']) - 3} more)"
            print(f"  CPT {cpt_code}: {data['count']} rejections across {len(data['practices'])} practice(s)")
            print(f"    Practices: {practices_list}")
        print()
    
    # Detailed breakdown by practice
    if all_rejection_patterns:
        print("Detailed Rejection Patterns by Practice:")
        print("-" * 80)
        for pattern in sorted(all_rejection_patterns, key=lambda x: x['total_rejections'], reverse=True)[:20]:
            print(f"\n{pattern['practice_name']} - CPT {pattern['cpt_code']}:")
            print(f"  Rejections: {pattern['total_rejections']} ({pattern['rejection_rate']:.1%} rejection rate)")
            issues = []
            if pattern.get('missing_submitted_date', 0) > 0:
                issues.append(f"Missing Submitted Date ({pattern['missing_submitted_date']})")
            if pattern.get('missing_patient_id', 0) > 0:
                issues.append(f"Missing Patient ID ({pattern['missing_patient_id']})")
            if pattern.get('missing_provider_id', 0) > 0:
                issues.append(f"Missing Provider ID ({pattern['missing_provider_id']})")
            if pattern.get('missing_service_date', 0) > 0:
                issues.append(f"Missing Service Date ({pattern['missing_service_date']})")
            if pattern.get('missing_line_items', 0) > 0:
                issues.append(f"Missing Line Items ({pattern['missing_line_items']})")
            if pattern.get('invalid_date_order', 0) > 0:
                issues.append(f"Invalid Date Order ({pattern['invalid_date_order']})")
            if pattern.get('missing_cpt_in_line_items', 0) > 0:
                issues.append(f"Missing CPT in Line Items ({pattern['missing_cpt_in_line_items']})")
            if pattern.get('invalid_cpt_count', 0) > 0:
                issues.append(f"Invalid CPT Count ({pattern['invalid_cpt_count']})")
            if pattern.get('missing_billed_amount', 0) > 0:
                issues.append(f"Missing Billed Amount ({pattern['missing_billed_amount']})")
            
            if issues:
                print(f"  Issues: {', '.join(issues)}")
            else:
                print(f"  ⚠️  No specific field issues detected (rejection risk score: {pattern['rejection_risk_score']})")
    
    print()
    print("=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()


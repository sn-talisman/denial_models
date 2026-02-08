#!/usr/bin/env python3
"""Analyze denial patterns across all practices to ensure comprehensive capture."""

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


def get_performance_summary(practice_id: str, days_back: int) -> dict:
    """Get performance summary for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/performance-summary?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error getting performance summary: {e}")
        return None


def get_carc_rarc_analysis(practice_id: str, days_back: int) -> dict:
    """Get CARC/RARC analysis for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/denial-reasons?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error getting CARC/RARC analysis: {e}")
        return None


def get_cpt_carc_correlation(practice_id: str, days_back: int) -> dict:
    """Get CPT-CARC correlation for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/cpt-carc-correlation?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error getting CPT-CARC correlation: {e}")
        return None


def get_payer_performance(practice_id: str, days_back: int) -> dict:
    """Get payer performance for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/payer-performance?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error getting payer performance: {e}")
        return None


def get_cpt_performance(practice_id: str, days_back: int) -> dict:
    """Get CPT performance for a practice."""
    url = f"{BASE_URL}/api/v1/analytics/practice/{practice_id}/cpt-performance?days_back={days_back}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️  Error getting CPT performance: {e}")
        return None


def main():
    print("=" * 80)
    print("Denial Pattern Analysis - All Practices")
    print("=" * 80)
    print(f"Days Back: {DAYS_BACK}")
    print(f"API Base URL: {BASE_URL}")
    print()
    
    # Get all practices
    practices = get_all_practices()
    print(f"Found {len(practices)} practices with claims")
    print()
    
    # Analyze each practice
    all_denial_data = []
    practices_with_denials = 0
    total_denials = 0
    total_claims = 0
    
    # Aggregate denial data across all practices
    carc_summary = defaultdict(lambda: {'count': 0, 'amount': 0.0, 'practices': set()})
    rarc_summary = defaultdict(lambda: {'count': 0, 'amount': 0.0, 'practices': set()})
    payer_denial_summary = defaultdict(lambda: {'claims': 0, 'denials': 0, 'amount': 0.0, 'practices': set()})
    cpt_denial_summary = defaultdict(lambda: {'claims': 0, 'denials': 0, 'amount': 0.0, 'practices': set()})
    cpt_carc_combinations = defaultdict(lambda: {'count': 0, 'amount': 0.0, 'practices': set()})
    
    for idx, practice in enumerate(practices, 1):
        practice_id = practice['practice_id']
        practice_name = practice['practice_name']
        
        print(f"[{idx}/{len(practices)}] Analyzing {practice_name}...")
        
        # Get performance summary
        perf_summary = get_performance_summary(practice_id, DAYS_BACK)
        if perf_summary:
            denied_count = perf_summary.get('denied_claims', 0)
            total_claims_practice = perf_summary.get('total_claims', 0)
            denial_rate = perf_summary.get('denial_rate', 0.0)
            denied_amount = perf_summary.get('denied_amount', 0.0)
            
            total_claims += total_claims_practice
            
            if denied_count > 0:
                practices_with_denials += 1
                total_denials += denied_count
                
                print(f"  ✅ {denied_count} denied claims ({denial_rate:.1%} denial rate, ${denied_amount:,.2f})")
                
                all_denial_data.append({
                    'practice_name': practice_name,
                    'practice_id': practice_id,
                    'total_claims': total_claims_practice,
                    'denied_claims': denied_count,
                    'denial_rate': denial_rate,
                    'denied_amount': denied_amount,
                })
            else:
                print(f"  ℹ️  No denials found")
        
        # Get CARC/RARC analysis
        carc_rarc = get_carc_rarc_analysis(practice_id, DAYS_BACK)
        if carc_rarc:
            for carc in carc_rarc.get('carc_codes', [])[:10]:
                carc_code = carc['carc_code']
                carc_summary[carc_code]['count'] += carc['occurrence_count']
                carc_summary[carc_code]['amount'] += carc['total_adjustment_amount']
                carc_summary[carc_code]['practices'].add(practice_name)
            
            for rarc in carc_rarc.get('rarc_codes', [])[:10]:
                rarc_code = rarc['rarc_code']
                rarc_summary[rarc_code]['count'] += rarc['occurrence_count']
                rarc_summary[rarc_code]['amount'] += rarc['total_adjustment_amount']
                rarc_summary[rarc_code]['practices'].add(practice_name)
        
        # Get payer performance
        payer_perf = get_payer_performance(practice_id, DAYS_BACK)
        if payer_perf:
            for payer in payer_perf.get('payers', [])[:10]:
                payer_name = payer['payer_name']
                payer_denial_summary[payer_name]['claims'] += payer['total_claims']
                payer_denial_summary[payer_name]['denials'] += payer['denied_claims']
                payer_denial_summary[payer_name]['amount'] += payer['denied_amount']
                payer_denial_summary[payer_name]['practices'].add(practice_name)
        
        # Get CPT performance
        cpt_perf = get_cpt_performance(practice_id, DAYS_BACK)
        if cpt_perf:
            for cpt in cpt_perf.get('cpt_codes', [])[:10]:
                cpt_code = cpt['cpt_code']
                cpt_denial_summary[cpt_code]['claims'] += cpt['total_claims']
                cpt_denial_summary[cpt_code]['denials'] += cpt['denied_claims']
                cpt_denial_summary[cpt_code]['amount'] += cpt['denied_amount']
                cpt_denial_summary[cpt_code]['practices'].add(practice_name)
        
        # Get CPT-CARC correlation
        cpt_carc = get_cpt_carc_correlation(practice_id, DAYS_BACK)
        if cpt_carc:
            for combo in cpt_carc.get('cpt_carc', [])[:10]:
                key = f"{combo['cpt_code']}-{combo['carc_code']}"
                cpt_carc_combinations[key]['count'] += combo['occurrence_count']
                cpt_carc_combinations[key]['amount'] += combo['total_adjustment_amount']
                cpt_carc_combinations[key]['practices'].add(practice_name)
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Practices Analyzed: {len(practices)}")
    print(f"Total Claims: {total_claims:,}")
    print(f"Practices with Denials: {practices_with_denials}")
    print(f"Total Denials: {total_denials:,}")
    overall_denial_rate = (total_denials / total_claims * 100) if total_claims > 0 else 0
    print(f"Overall Denial Rate: {overall_denial_rate:.2f}%")
    print()
    
    # Top practices by denial rate
    if all_denial_data:
        print("Top Practices by Denial Rate:")
        print("-" * 80)
        sorted_practices = sorted(all_denial_data, key=lambda x: x['denial_rate'], reverse=True)
        for practice in sorted_practices[:10]:
            print(f"  {practice['practice_name']}:")
            print(f"    Denial Rate: {practice['denial_rate']:.1%}")
            print(f"    Denied Claims: {practice['denied_claims']:,} / {practice['total_claims']:,}")
            print(f"    Denied Amount: ${practice['denied_amount']:,.2f}")
        print()
    
    # Top CARC codes
    if carc_summary:
        print("Top CARC (Claim Adjustment Reason) Codes:")
        print("-" * 80)
        sorted_carcs = sorted(carc_summary.items(), key=lambda x: x[1]['amount'], reverse=True)
        for carc_code, data in sorted_carcs[:15]:
            practices_list = ', '.join(list(data['practices'])[:3])
            if len(data['practices']) > 3:
                practices_list += f" (+{len(data['practices']) - 3} more)"
            print(f"  CARC {carc_code}: {data['count']:,} occurrences, ${data['amount']:,.2f}")
            print(f"    Practices: {practices_list}")
        print()
    
    # Top payers by denial amount
    if payer_denial_summary:
        print("Top Payers by Denial Amount:")
        print("-" * 80)
        sorted_payers = sorted(payer_denial_summary.items(), key=lambda x: x[1]['amount'], reverse=True)
        for payer_name, data in sorted_payers[:15]:
            denial_rate = (data['denials'] / data['claims'] * 100) if data['claims'] > 0 else 0
            practices_list = ', '.join(list(data['practices'])[:3])
            if len(data['practices']) > 3:
                practices_list += f" (+{len(data['practices']) - 3} more)"
            print(f"  {payer_name[:50]}:")
            print(f"    Denial Rate: {denial_rate:.1%} ({data['denials']:,}/{data['claims']:,} claims)")
            print(f"    Denied Amount: ${data['amount']:,.2f}")
            print(f"    Practices: {practices_list}")
        print()
    
    # Top CPT codes by denial amount
    if cpt_denial_summary:
        print("Top CPT Codes by Denial Amount:")
        print("-" * 80)
        sorted_cpts = sorted(cpt_denial_summary.items(), key=lambda x: x[1]['amount'], reverse=True)
        for cpt_code, data in sorted_cpts[:15]:
            denial_rate = (data['denials'] / data['claims'] * 100) if data['claims'] > 0 else 0
            practices_list = ', '.join(list(data['practices'])[:3])
            if len(data['practices']) > 3:
                practices_list += f" (+{len(data['practices']) - 3} more)"
            print(f"  CPT {cpt_code}:")
            print(f"    Denial Rate: {denial_rate:.1%} ({data['denials']:,}/{data['claims']:,} claims)")
            print(f"    Denied Amount: ${data['amount']:,.2f}")
            print(f"    Practices: {practices_list}")
        print()
    
    # Top CPT-CARC combinations
    if cpt_carc_combinations:
        print("Top CPT-CARC Combinations:")
        print("-" * 80)
        sorted_combos = sorted(cpt_carc_combinations.items(), key=lambda x: x[1]['amount'], reverse=True)
        for combo_key, data in sorted_combos[:15]:
            cpt, carc = combo_key.split('-')
            practices_list = ', '.join(list(data['practices'])[:2])
            if len(data['practices']) > 2:
                practices_list += f" (+{len(data['practices']) - 2} more)"
            print(f"  CPT {cpt} + CARC {carc}: {data['count']:,} occurrences, ${data['amount']:,.2f}")
            print(f"    Practices: {practices_list}")
        print()
    
    print("=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()


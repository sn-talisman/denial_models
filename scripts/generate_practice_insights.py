#!/usr/bin/env python3
"""Generate actionable practice insights with prioritized recommendations."""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer_optimized import engineer_features_batch_optimized
from src.models.denial_predictor.predictor import DenialPredictor
from src.utils.logging_config import configure_logging

load_dotenv()
configure_logging()


async def generate_practice_insights():
    """Generate actionable practice insights markdown."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        sys.exit(1)
    
    model_path = Path("models/denial_predictor_lightgbm.pkl")
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        sys.exit(1)
    
    repository = get_repository()
    predictor = DenialPredictor(model_path=model_path)
    
    try:
        # Fetch claims from last 365 days
        date_to = date.today()
        date_from = date_to - timedelta(days=365)
        
        print("📊 Fetching claims and engineering features...")
        claims = await repository.get_claims(
            date_from=date_from,
            date_to=date_to,
        )
        
        if not claims:
            print("❌ No claims found")
            return
        
        # Engineer features
        df = await engineer_features_batch_optimized(
            claims=claims,
            repository=repository,
            reference_date=date_to,
        )
        
        if df.empty:
            print("❌ No features generated")
            return
        
        # Make predictions
        exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                       'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                       'cpt_code', 'cpt_category', 'is_denied']
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        features_df = df[feature_cols].copy()
        
        # Convert object columns to numeric
        for col in features_df.columns:
            if features_df[col].dtype == 'object':
                try:
                    features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
                except:
                    pass
        
        features_df = features_df.fillna(0)
        for col in features_df.columns:
            if features_df[col].dtype == 'object':
                features_df[col] = features_df[col].astype(float)
        
        predictions_df = predictor.predict_batch(features_df)
        
        # Add original data
        claim_to_practice = {c.claim_id: c.practice_id for c in claims}
        claim_to_payer = {c.claim_id: c.payer_id for c in claims}
        claim_to_provider = {c.claim_id: c.provider_id for c in claims}
        claim_to_service_date = {c.claim_id: c.service_date_from for c in claims}
        claim_to_submitted_date = {c.claim_id: c.submitted_date for c in claims}
        
        predictions_df['claim_id'] = df['claim_id'].values
        predictions_df['practice_id'] = predictions_df['claim_id'].map(claim_to_practice)
        predictions_df['payer_id'] = predictions_df['claim_id'].map(claim_to_payer)
        predictions_df['provider_id'] = predictions_df['claim_id'].map(claim_to_provider)
        predictions_df['service_date'] = predictions_df['claim_id'].map(claim_to_service_date)
        predictions_df['submitted_date'] = predictions_df['claim_id'].map(claim_to_submitted_date)
        predictions_df['is_denied'] = df['is_denied'].values if 'is_denied' in df.columns else [False] * len(df)
        predictions_df['total_billed_amount'] = df['total_billed_amount'].values if 'total_billed_amount' in df.columns else [0] * len(df)
        predictions_df['total_paid_amount'] = df['total_paid_amount'].values if 'total_paid_amount' in df.columns else [0] * len(df)
        predictions_df['payment_ratio'] = df['payment_ratio'].values if 'payment_ratio' in df.columns else [0] * len(df)
        predictions_df['has_partial_denial'] = df['has_partial_denial'].values if 'has_partial_denial' in df.columns else [False] * len(df)
        predictions_df['adjustment_ratio'] = df['adjustment_ratio'].values if 'adjustment_ratio' in df.columns else [0] * len(df)
        predictions_df['primary_cpt_code'] = df['primary_cpt_code'].values if 'primary_cpt_code' in df.columns else [''] * len(df)
        
        # Get practice and payer names
        practices = await repository.get_practices()
        payers = await repository.get_payers()
        
        practice_map = {p.practice_id: p.name for p in practices}
        payer_map = {p.payer_id: p.name for p in payers}
        
        predictions_df['practice_name'] = predictions_df['practice_id'].map(practice_map)
        predictions_df['payer_name'] = predictions_df['payer_id'].map(payer_map)
        
        # Fill missing names
        missing_practice_mask = predictions_df['practice_name'].isna() & predictions_df['practice_id'].notna()
        predictions_df.loc[missing_practice_mask, 'practice_name'] = 'Practice ' + predictions_df.loc[missing_practice_mask, 'practice_id'].astype(str).str[:8]
        
        missing_payer_mask = predictions_df['payer_name'].isna() & predictions_df['payer_id'].notna()
        predictions_df.loc[missing_payer_mask, 'payer_name'] = 'Payer ' + predictions_df.loc[missing_payer_mask, 'payer_id'].astype(str).str[:20]
        
        print("📊 Generating actionable insights...")
        
        # Generate markdown
        md_content = generate_actionable_markdown(predictions_df)
        
        # Save to file
        output_file = Path("PRACTICE_INSIGHTS.md")
        output_file.write_text(md_content)
        
        print(f"✅ Generated {output_file}")
        print(f"\n{md_content[:2000]}...")  # Print first 2000 chars
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repository.close()


def generate_actionable_markdown(df: pd.DataFrame) -> str:
    """Generate markdown with actionable, prioritized insights."""
    
    md = []
    md.append("# Practice Performance Insights & Actionable Recommendations")
    md.append("")
    md.append(f"*Generated from {len(df):,} claims*")
    md.append("")
    md.append("---")
    md.append("")
    
    # Calculate overall benchmarks
    overall_denial_rate = df['is_denied'].mean()
    overall_avg_prob = df['denial_probability'].mean()
    
    # Get unique practices
    practices = df['practice_id'].dropna().unique()
    
    for practice_id in practices:
        practice_data = df[df['practice_id'] == practice_id].copy()
        practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
        
        md.append(f"## {practice_name}")
        md.append("")
        
        # Overall statistics
        total = len(practice_data)
        denied = practice_data['is_denied'].sum()
        denied_rate = denied / total if total > 0 else 0
        
        total_billed = practice_data['total_billed_amount'].sum()
        total_paid = practice_data['total_paid_amount'].sum()
        denied_amount = practice_data[practice_data['is_denied']]['total_billed_amount'].sum()
        potential_revenue_recovery = denied_amount
        
        avg_probability = practice_data['denial_probability'].mean()
        high_risk = (practice_data['risk_level'] == 'high').sum()
        high_risk_pct = high_risk / total if total > 0 else 0
        
        md.append("### 📊 Performance Summary")
        md.append("")
        md.append("| Metric | Value | vs Overall |")
        md.append("|--------|-------|------------|")
        md.append(f"| Total Claims | {total:,} | - |")
        md.append(f"| Denial Rate | {denied_rate:.1%} | {'🔴 +' if denied_rate > overall_denial_rate else '🟢 -'}{abs(denied_rate - overall_denial_rate):.1%} |")
        md.append(f"| Total Billed | ${total_billed:,.2f} | - |")
        md.append(f"| Total Paid | ${total_paid:,.2f} | - |")
        md.append(f"| **Denied Amount** | **${denied_amount:,.2f}** | **Potential Recovery** |")
        md.append(f"| Avg Denial Probability | {avg_probability:.3f} | {'🔴 +' if avg_probability > overall_avg_prob else '🟢 -'}{abs(avg_probability - overall_avg_prob):.3f} |")
        md.append(f"| High Risk Claims | {high_risk} ({high_risk_pct:.1%}) | - |")
        md.append("")
        
        # PRIORITIZED ACTION ITEMS
        md.append("### 🎯 Prioritized Action Items")
        md.append("")
        
        action_items = []
        
        # 1. Payer-specific issues (highest impact)
        payer_analysis = analyze_payer_patterns(practice_data)
        for payer_issue in payer_analysis[:5]:  # Top 5 payer issues
            action_items.append({
                'priority': payer_issue['priority'],
                'title': payer_issue['title'],
                'impact': payer_issue['financial_impact'],
                'recommendation': payer_issue['recommendation'],
                'details': payer_issue.get('details', '')
            })
        
        # 2. CPT code issues
        cpt_analysis = analyze_cpt_patterns(practice_data)
        for cpt_issue in cpt_analysis[:5]:  # Top 5 CPT issues
            action_items.append({
                'priority': cpt_issue['priority'],
                'title': cpt_issue['title'],
                'impact': cpt_issue['financial_impact'],
                'recommendation': cpt_issue['recommendation'],
                'details': cpt_issue.get('details', '')
            })
        
        # 3. Temporal patterns
        temporal_analysis = analyze_temporal_patterns(practice_data)
        for temp_issue in temporal_analysis[:3]:  # Top 3 temporal issues
            action_items.append({
                'priority': temp_issue['priority'],
                'title': temp_issue['title'],
                'impact': temp_issue['financial_impact'],
                'recommendation': temp_issue['recommendation'],
                'details': temp_issue.get('details', '')
            })
        
        # 4. Provider patterns
        provider_analysis = analyze_provider_patterns(practice_data)
        for prov_issue in provider_analysis[:3]:  # Top 3 provider issues
            action_items.append({
                'priority': prov_issue['priority'],
                'title': prov_issue['title'],
                'impact': prov_issue['financial_impact'],
                'recommendation': prov_issue['recommendation'],
                'details': prov_issue.get('details', '')
            })
        
        # Sort by priority (financial impact)
        action_items.sort(key=lambda x: x['impact'], reverse=True)
        
        for idx, item in enumerate(action_items[:10], 1):  # Top 10 action items
            md.append(f"#### {idx}. {item['title']}")
            md.append("")
            md.append(f"**Financial Impact**: ${item['impact']:,.2f} in denied claims")
            md.append("")
            md.append(f"**Recommendation**: {item['recommendation']}")
            if item['details']:
                md.append("")
                md.append(f"*{item['details']}*")
            md.append("")
        
        if not action_items:
            md.append("*No specific action items identified. Practice performance is within normal parameters.*")
            md.append("")
        
        # DETAILED BREAKDOWNS
        md.append("### 📋 Detailed Analysis")
        md.append("")
        
        # Payer breakdown (aggregated properly)
        md.append("#### Performance by Payer")
        md.append("")
        
        payer_summary = practice_data.groupby('payer_name').agg({
            'claim_id': 'count',
            'is_denied': 'sum',
            'total_billed_amount': 'sum',
            'total_paid_amount': 'sum',
            'denial_probability': 'mean'
        }).reset_index()
        
        payer_summary.columns = ['Payer', 'Total Claims', 'Denied', 'Total Billed', 'Total Paid', 'Avg Denial Prob']
        payer_summary['Denial Rate'] = payer_summary['Denied'] / payer_summary['Total Claims']
        
        # Calculate denied amounts per payer
        denied_by_payer = practice_data[practice_data['is_denied']].groupby('payer_name')['total_billed_amount'].sum().reset_index()
        denied_by_payer.columns = ['Payer', 'Denied Amount']
        payer_summary = payer_summary.merge(denied_by_payer, on='Payer', how='left')
        payer_summary['Denied Amount'] = payer_summary['Denied Amount'].fillna(0)
        payer_summary = payer_summary.sort_values('Denied Amount', ascending=False)
        
        md.append("| Payer | Claims | Denial Rate | Denied Amount | Avg Risk |")
        md.append("|-------|--------|-------------|---------------|----------|")
        for _, row in payer_summary.head(10).iterrows():
            md.append(f"| {row['Payer'][:40]} | {int(row['Total Claims'])} | {row['Denial Rate']:.1%} | ${row['Denied Amount']:,.2f} | {row['Avg Denial Prob']:.2f} |")
        md.append("")
        
        # CPT code breakdown
        md.append("#### Performance by CPT Code")
        md.append("")
        
        cpt_summary = practice_data[practice_data['primary_cpt_code'].notna() & (practice_data['primary_cpt_code'] != '')].groupby('primary_cpt_code').agg({
            'claim_id': 'count',
            'is_denied': 'sum',
            'total_billed_amount': 'sum',
            'denial_probability': 'mean'
        }).reset_index()
        
        if len(cpt_summary) > 0:
            cpt_summary.columns = ['CPT Code', 'Total Claims', 'Denied', 'Total Billed', 'Avg Denial Prob']
            cpt_summary['Denial Rate'] = cpt_summary['Denied'] / cpt_summary['Total Claims']
            
            # Calculate denied amounts per CPT
            denied_by_cpt = practice_data[
                (practice_data['is_denied']) & 
                (practice_data['primary_cpt_code'].notna()) & 
                (practice_data['primary_cpt_code'] != '')
            ].groupby('primary_cpt_code')['total_billed_amount'].sum().reset_index()
            denied_by_cpt.columns = ['CPT Code', 'Denied Amount']
            cpt_summary = cpt_summary.merge(denied_by_cpt, on='CPT Code', how='left')
            cpt_summary['Denied Amount'] = cpt_summary['Denied Amount'].fillna(0)
            cpt_summary = cpt_summary.sort_values('Denied Amount', ascending=False)
            
            md.append("| CPT Code | Claims | Denial Rate | Denied Amount | Avg Risk |")
            md.append("|----------|--------|-------------|---------------|----------|")
            for _, row in cpt_summary.head(10).iterrows():
                md.append(f"| {row['CPT Code']} | {int(row['Total Claims'])} | {row['Denial Rate']:.1%} | ${row['Denied Amount']:,.2f} | {row['Avg Denial Prob']:.2f} |")
            md.append("")
        
        # High-risk claims
        md.append("#### High-Risk Claims Requiring Immediate Attention")
        md.append("")
        
        high_risk_claims = practice_data[practice_data['risk_level'] == 'high'].sort_values('denial_probability', ascending=False)
        if len(high_risk_claims) > 0:
            md.append("| Claim ID | Payer | CPT | Denial Prob | Billed Amount |")
            md.append("|----------|-------|-----|-------------|---------------|")
            for _, claim in high_risk_claims.head(20).iterrows():
                claim_id_short = str(claim['claim_id'])[:8] if pd.notna(claim['claim_id']) else 'N/A'
                payer_short = str(claim['payer_name'])[:25] if pd.notna(claim['payer_name']) else 'Unknown'
                cpt_short = str(claim['primary_cpt_code'])[:10] if pd.notna(claim['primary_cpt_code']) else 'N/A'
                md.append(f"| {claim_id_short} | {payer_short} | {cpt_short} | {claim['denial_probability']:.1%} | ${claim['total_billed_amount']:,.2f} |")
        else:
            md.append("*No high-risk claims identified.*")
        md.append("")
        
        md.append("---")
        md.append("")
    
    return "\n".join(md)


def analyze_payer_patterns(practice_data: pd.DataFrame) -> list:
    """Analyze payer-specific denial patterns and return actionable insights."""
    insights = []
    
    payer_groups = practice_data.groupby('payer_name')
    
    for payer_name, payer_data in payer_groups:
        if pd.isna(payer_name) or payer_name == '':
            continue
            
        total = len(payer_data)
        denied = payer_data['is_denied'].sum()
        denial_rate = denied / total if total > 0 else 0
        denied_amount = payer_data[payer_data['is_denied']]['total_billed_amount'].sum()
        
        if total < 3:  # Skip if too few claims
            continue
        
        # High denial rate payer
        if denial_rate > 0.5:
            insights.append({
                'priority': 'HIGH',
                'title': f'High Denial Rate with {payer_name[:40]}',
                'financial_impact': denied_amount,
                'recommendation': f'Review documentation requirements and coding practices for {payer_name[:30]}. Consider payer-specific training for billing staff.',
                'details': f'{denial_rate:.1%} denial rate on {total} claims (${denied_amount:,.2f} at risk)'
            })
        
        # Identify problematic CPT codes for this payer
        payer_cpt = payer_data[payer_data['is_denied']].groupby('primary_cpt_code').agg({
            'claim_id': 'count',
            'total_billed_amount': 'sum'
        }).reset_index()
        
        if len(payer_cpt) > 0:
            payer_cpt = payer_cpt.sort_values('total_billed_amount', ascending=False)
            top_problem_cpt = payer_cpt.iloc[0]
            
            if top_problem_cpt['claim_id'] >= 3:  # At least 3 denied claims
                insights.append({
                    'priority': 'MEDIUM',
                    'title': f'CPT {top_problem_cpt["primary_cpt_code"]} Denials with {payer_name[:30]}',
                    'financial_impact': top_problem_cpt['total_billed_amount'],
                    'recommendation': f'Review CPT {top_problem_cpt["primary_cpt_code"]} coding and documentation for {payer_name[:30]}. Verify medical necessity documentation.',
                    'details': f'{int(top_problem_cpt["claim_id"])} denied claims totaling ${top_problem_cpt["total_billed_amount"]:,.2f}'
                })
    
    return insights


def analyze_cpt_patterns(practice_data: pd.DataFrame) -> list:
    """Analyze CPT code-specific denial patterns."""
    insights = []
    
    cpt_data = practice_data[practice_data['primary_cpt_code'].notna() & (practice_data['primary_cpt_code'] != '')]
    
    if len(cpt_data) == 0:
        return insights
    
    cpt_groups = cpt_data.groupby('primary_cpt_code')
    
    for cpt_code, cpt_claims in cpt_groups:
        total = len(cpt_claims)
        denied = cpt_claims['is_denied'].sum()
        denial_rate = denied / total if total > 0 else 0
        denied_amount = cpt_claims[cpt_claims['is_denied']]['total_billed_amount'].sum()
        
        if total < 5:  # Need at least 5 claims for meaningful analysis
            continue
        
        # High denial rate CPT
        if denial_rate > 0.4:
            # Check which payers are problematic
            payer_breakdown = cpt_claims[cpt_claims['is_denied']].groupby('payer_name')['total_billed_amount'].sum()
            if len(payer_breakdown) > 0:
                top_payer = payer_breakdown.idxmax()
                top_payer_amount = payer_breakdown.max()
                
                insights.append({
                    'priority': 'HIGH' if denial_rate > 0.6 else 'MEDIUM',
                    'title': f'High Denial Rate for CPT {cpt_code}',
                    'financial_impact': denied_amount,
                    'recommendation': f'Review coding accuracy and documentation for CPT {cpt_code}. Primary issue with {top_payer[:30]}. Verify code selection and medical necessity.',
                    'details': f'{denial_rate:.1%} denial rate ({denied}/{total} claims, ${denied_amount:,.2f} at risk). {top_payer[:30]} accounts for ${top_payer_amount:,.2f}.'
                })
    
    return insights


def analyze_temporal_patterns(practice_data: pd.DataFrame) -> list:
    """Analyze temporal patterns (day of week, month, etc.)."""
    insights = []
    
    # Day of week analysis
    if 'submitted_date' in practice_data.columns and practice_data['submitted_date'].notna().any():
        practice_data['submitted_date'] = pd.to_datetime(practice_data['submitted_date'], errors='coerce')
        practice_data['day_of_week'] = practice_data['submitted_date'].dt.day_name()
        
        dow_groups = practice_data.groupby('day_of_week')
        dow_denial_rates = {}
        
        for dow, dow_data in dow_groups:
            if len(dow_data) < 10:  # Need sufficient data
                continue
            denial_rate = dow_data['is_denied'].mean()
            denied_amount = dow_data[dow_data['is_denied']]['total_billed_amount'].sum()
            dow_denial_rates[dow] = {'rate': denial_rate, 'amount': denied_amount, 'count': len(dow_data)}
        
        if len(dow_denial_rates) > 0:
            # Find worst day
            worst_day = max(dow_denial_rates.items(), key=lambda x: x[1]['rate'])
            best_day = min(dow_denial_rates.items(), key=lambda x: x[1]['rate'])
            
            if worst_day[1]['rate'] > best_day[1]['rate'] + 0.15:  # 15% difference
                insights.append({
                    'priority': 'MEDIUM',
                    'title': f'Higher Denial Rate on {worst_day[0]}',
                    'financial_impact': worst_day[1]['amount'],
                    'recommendation': f'Review claim submission process on {worst_day[0]}. May indicate rushed submissions or staffing issues.',
                    'details': f'{worst_day[1]["rate"]:.1%} denial rate on {worst_day[0]} vs {best_day[1]["rate"]:.1%} on {best_day[0]} ({worst_day[1]["count"]} claims)'
                })
    
    return insights


def analyze_provider_patterns(practice_data: pd.DataFrame) -> list:
    """Analyze provider-specific patterns."""
    insights = []
    
    if 'provider_id' not in practice_data.columns:
        return insights
    
    provider_data = practice_data[practice_data['provider_id'].notna()]
    
    if len(provider_data) == 0:
        return insights
    
    provider_groups = provider_data.groupby('provider_id')
    
    for provider_id, prov_claims in provider_groups:
        total = len(prov_claims)
        denied = prov_claims['is_denied'].sum()
        denial_rate = denied / total if total > 0 else 0
        denied_amount = prov_claims[prov_claims['is_denied']]['total_billed_amount'].sum()
        
        if total < 10:  # Need sufficient claims
            continue
        
        # High denial rate provider
        if denial_rate > 0.4:
            provider_short = str(provider_id)[:8]
            insights.append({
                'priority': 'MEDIUM',
                'title': f'High Denial Rate for Provider {provider_short}',
                'financial_impact': denied_amount,
                'recommendation': f'Review coding and documentation practices for Provider {provider_short}. Consider additional training or coding review.',
                'details': f'{denial_rate:.1%} denial rate on {total} claims (${denied_amount:,.2f} at risk)'
            })
    
    return insights


if __name__ == "__main__":
    asyncio.run(generate_practice_insights())

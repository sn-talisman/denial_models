"""Helper functions for practice analytics endpoints."""

from typing import Optional, Dict, Any
from datetime import date, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict

from src.data_access.base_repository import ClaimsRepository
from src.models.denial_predictor.predictor import DenialPredictor


async def get_practice_data(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
    predictor: DenialPredictor,
) -> pd.DataFrame:
    """Get processed practice data with predictions.
    
    Args:
        practice_id: Practice GUID
        days_back: Number of days to look back
        repository: Database repository
        predictor: Denial predictor instance
        
    Returns:
        DataFrame with claims, features, and predictions
    """
    from src.pipelines.feature_engineering.feature_engineer_optimized import engineer_features_batch_optimized
    
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    
    # Fetch claims for this practice
    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    
    if not claims:
        return pd.DataFrame()
    
    # Engineer features
    df = await engineer_features_batch_optimized(
        claims=claims,
        repository=repository,
        reference_date=date_to,
    )
    
    if df.empty:
        return pd.DataFrame()
    
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
    
    return predictions_df


def get_performance_insights(practice_data: pd.DataFrame) -> dict:
    """Get additional performance insights for a practice."""
    insights = {
        'trends': {},
        'comparisons': {},
        'key_issues': [],
        'risk_factors': [],
    }
    
    total = len(practice_data)
    if total == 0:
        return insights
    
    denied = practice_data['is_denied'].sum()
    denied_rate = denied / total if total > 0 else 0
    
    # Calculate daily denial trends (for frontend chart)
    if 'service_date' in practice_data.columns and 'is_denied' in practice_data.columns:
        # Group by service date to get daily denial rates
        # Filter out rows with invalid dates if necessary
        daily_data = practice_data[practice_data['service_date'].notna()].copy()
        
        if not daily_data.empty:
            daily_stats = daily_data.groupby('service_date').agg({
                'is_denied': ['sum', 'count']
            })
            
            # Flatten columns
            daily_stats.columns = ['denied_count', 'total_count']
            daily_stats['denial_rate'] = daily_stats['denied_count'] / daily_stats['total_count']
            
            # Sort by date
            daily_stats = daily_stats.sort_index()
            
            # Populate trends dict {date_str: rate_float}
            insights['trends'] = {
                str(date): float(row['denial_rate']) 
                for date, row in daily_stats.iterrows()
            }
            
            # Add payment metrics to a separate key if needed (not used by current frontend)
            if 'payment_ratio' in practice_data.columns:
                insights['payment_metrics'] = {
                    'avg_payment_ratio': float(practice_data['payment_ratio'].mean()),
                    'low_payment_claims': int((practice_data['payment_ratio'] < 0.5).sum())
                }
    
    # Identify high-risk payers
    if 'payer_name' in practice_data.columns:
        payer_denial_rates = practice_data.groupby('payer_name').agg({
            'is_denied': ['sum', 'count']
        })
        payer_denial_rates.columns = ['denied', 'total']
        payer_denial_rates['denial_rate'] = payer_denial_rates['denied'] / payer_denial_rates['total']
        high_risk_payers = payer_denial_rates[payer_denial_rates['denial_rate'] > 0.5].index.tolist()
        insights['risk_factors'].extend([f"High denial rate with {payer}" for payer in high_risk_payers[:5]])
    
    # Identify high-risk CPT codes
    if 'primary_cpt_code' in practice_data.columns:
        cpt_denial_rates = practice_data.groupby('primary_cpt_code').agg({
            'is_denied': ['sum', 'count']
        })
        cpt_denial_rates.columns = ['denied', 'total']
        cpt_denial_rates['denial_rate'] = cpt_denial_rates['denied'] / cpt_denial_rates['total']
        high_risk_cpts = cpt_denial_rates[cpt_denial_rates['denial_rate'] > 0.5].index.tolist()
        insights['risk_factors'].extend([f"High denial rate for CPT {cpt}" for cpt in high_risk_cpts[:5]])
    
    # Key issues
    if denied_rate > 0.5:
        insights['key_issues'].append(f"Very high denial rate ({denied_rate:.1%}) - above 50%")
    elif denied_rate > 0.3:
        insights['key_issues'].append(f"High denial rate ({denied_rate:.1%}) - above 30%")
    
    if 'high_risk_claims' in practice_data.columns:
        high_risk_pct = (practice_data['risk_level'] == 'high').sum() / total if total > 0 else 0
        if high_risk_pct > 0.5:
            insights['key_issues'].append(f"High percentage of high-risk claims ({high_risk_pct:.1%})")
    
    return insights


def calculate_performance_summary(practice_data: pd.DataFrame, overall_denial_rate: float, overall_avg_prob: float) -> dict:
    """Calculate performance summary for a practice."""
    total = len(practice_data)
    denied = practice_data['is_denied'].sum()
    denied_rate = denied / total if total > 0 else 0
    
    total_billed = practice_data['total_billed_amount'].sum()
    total_paid = practice_data['total_paid_amount'].sum()
    
    # Calculate denied amount: sum of billed amounts for denied claims
    # For partially denied claims, we could use adjustment_amount, but for consistency
    # we'll use the full billed amount (shows potential recovery)
    denied_amount = practice_data[practice_data['is_denied']]['total_billed_amount'].sum()
    
    # Also calculate adjustment amount for partially denied claims
    if 'adjustment_amount' in practice_data.columns:
        # For partially denied claims, use the actual adjustment amount
        partially_denied = practice_data[
            (practice_data['is_denied']) & 
            (practice_data.get('is_partially_paid', pd.Series([False] * len(practice_data))) == True)
        ]
        if len(partially_denied) > 0:
            # Adjust denied_amount to use actual adjustments for partial denials
            partial_adjustments = partially_denied['adjustment_amount'].sum()
            full_denials = practice_data[
                (practice_data['is_denied']) & 
                (practice_data.get('is_partially_paid', pd.Series([False] * len(practice_data))) != True)
            ]['total_billed_amount'].sum()
            denied_amount = full_denials + partial_adjustments
    
    avg_probability = practice_data['denial_probability'].mean()
    high_risk = (practice_data['risk_level'] == 'high').sum()
    high_risk_pct = high_risk / total if total > 0 else 0
    
    # Get additional insights
    insights = get_performance_insights(practice_data)
    
    # Calculate recovery potential
    recovery_potential = denied_amount * 0.3  # Assume 30% recovery rate on appeals
    
    return {
        'total_claims': int(total),
        'denied_claims': int(denied),
        'denial_rate': float(denied_rate),
        'denial_rate_vs_overall': float(denied_rate - overall_denial_rate),
        'total_billed': float(total_billed),
        'total_paid': float(total_paid),
        'denied_amount': float(denied_amount),
        'recovery_potential': float(recovery_potential),
        'avg_denial_probability': float(avg_probability),
        'avg_probability_vs_overall': float(avg_probability - overall_avg_prob),
        'high_risk_claims': int(high_risk),
        'high_risk_pct': float(high_risk_pct),
        'insights': insights,
    }


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
                'financial_impact': float(denied_amount),
                'recommendation': f'Review documentation requirements and coding practices for {payer_name[:30]}. Consider payer-specific training for billing staff.',
                'details': f'{denial_rate:.1%} denial rate on {total} claims (${denied_amount:,.2f} at risk)',
                'payer_name': str(payer_name),
                'denial_rate': float(denial_rate),
                'total_claims': int(total),
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
                    'financial_impact': float(top_problem_cpt['total_billed_amount']),
                    'recommendation': f'Review CPT {top_problem_cpt["primary_cpt_code"]} coding and documentation for {payer_name[:30]}. Verify medical necessity documentation.',
                    'details': f'{int(top_problem_cpt["claim_id"])} denied claims totaling ${top_problem_cpt["total_billed_amount"]:,.2f}',
                    'payer_name': str(payer_name),
                    'cpt_code': str(top_problem_cpt['primary_cpt_code']),
                    'denied_claims': int(top_problem_cpt['claim_id']),
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
                    'financial_impact': float(denied_amount),
                    'recommendation': f'Review coding accuracy and documentation for CPT {cpt_code}. Primary issue with {top_payer[:30]}. Verify code selection and medical necessity.',
                    'details': f'{denial_rate:.1%} denial rate ({denied}/{total} claims, ${denied_amount:,.2f} at risk). {top_payer[:30]} accounts for ${top_payer_amount:,.2f}.',
                    'cpt_code': str(cpt_code),
                    'denial_rate': float(denial_rate),
                    'total_claims': int(total),
                    'denied_claims': int(denied),
                    'top_payer': str(top_payer),
                    'top_payer_amount': float(top_payer_amount),
                })
    
    return insights


def get_prioritized_action_items(
    practice_data: pd.DataFrame,
    carc_rarc_data: Optional[dict] = None,
    cpt_carc_data: Optional[dict] = None,
) -> list:
    """Get prioritized action items for a practice with enhanced insights."""
    action_items = []
    
    # 1. Payer-specific issues (highest impact)
    payer_analysis = analyze_payer_patterns(practice_data)
    for payer_issue in payer_analysis[:5]:  # Top 5 payer issues
        action_items.append({
            'priority': payer_issue['priority'],
            'title': payer_issue['title'],
            'financial_impact': payer_issue['financial_impact'],
            'recommendation': payer_issue['recommendation'],
            'details': payer_issue.get('details', ''),
            'type': 'payer',
            'payer_name': payer_issue.get('payer_name'),
            'cpt_code': payer_issue.get('cpt_code'),
        })
    
    # 2. CPT code issues
    cpt_analysis = analyze_cpt_patterns(practice_data)
    for cpt_issue in cpt_analysis[:5]:  # Top 5 CPT issues
        action_items.append({
            'priority': cpt_issue['priority'],
            'title': cpt_issue['title'],
            'financial_impact': cpt_issue['financial_impact'],
            'recommendation': cpt_issue['recommendation'],
            'details': cpt_issue.get('details', ''),
            'type': 'cpt',
            'cpt_code': cpt_issue.get('cpt_code'),
        })
    
    # 3. CARC code insights (if available)
    if carc_rarc_data and carc_rarc_data.get('carc_codes'):
        top_carc = carc_rarc_data['carc_codes'][0] if carc_rarc_data['carc_codes'] else None
        if top_carc and top_carc['total_adjustment_amount'] > 1000:
            from src.utils.constants import COMMON_CARC_CODES
            carc_code = top_carc['carc_code']
            carc_desc = COMMON_CARC_CODES.get(carc_code, f"CARC {carc_code}")
            
            # Determine recommendation based on CARC code
            if carc_code == 45:
                recommendation = "Review fee schedules and contracted rates. Consider renegotiating contracts or adjusting billing amounts to match payer fee schedules."
            elif carc_code == 16:
                recommendation = "Improve claim documentation completeness. Ensure all required information is included before submission."
            elif carc_code in [50, 54, 55, 56, 57, 58, 59]:
                recommendation = "Review medical necessity documentation. Ensure proper documentation supports the medical necessity of services."
            elif carc_code == 29:
                recommendation = "Improve timely filing processes. Submit claims within payer-specific deadlines."
            else:
                recommendation = f"Review denial reason: {carc_desc}. Investigate root cause and implement corrective actions."
            
            action_items.append({
                'priority': 'high' if top_carc['total_adjustment_amount'] > 10000 else 'medium',
                'title': f"Top Denial Reason: {carc_desc} (CARC {carc_code})",
                'financial_impact': float(top_carc['total_adjustment_amount']),
                'recommendation': recommendation,
                'details': f"{top_carc['occurrence_count']} occurrences affecting {top_carc['affected_claims']} claims",
                'type': 'carc',
                'carc_code': carc_code,
            })
    
    # 4. CPT-CARC correlation insights (if available)
    if cpt_carc_data and cpt_carc_data.get('cpt_carc'):
        top_combo = cpt_carc_data['cpt_carc'][0] if cpt_carc_data['cpt_carc'] else None
        if top_combo and top_combo['total_adjustment_amount'] > 5000:
            from src.utils.constants import COMMON_CARC_CODES
            carc_code = top_combo['carc_code']
            carc_desc = COMMON_CARC_CODES.get(carc_code, f"CARC {carc_code}")
            
            action_items.append({
                'priority': 'high' if top_combo['total_adjustment_amount'] > 20000 else 'medium',
                'title': f"CPT {top_combo['cpt_code']} + {carc_desc} (CARC {carc_code})",
                'financial_impact': float(top_combo['total_adjustment_amount']),
                'recommendation': f"Review CPT {top_combo['cpt_code']} billing practices. This procedure code frequently gets denied with {carc_desc}. Verify coding accuracy, documentation, and fee schedules.",
                'details': f"{top_combo['occurrence_count']} occurrences affecting {top_combo['affected_claims']} claims",
                'type': 'cpt_carc',
                'cpt_code': top_combo['cpt_code'],
                'carc_code': carc_code,
            })
    
    # Sort by priority (financial impact)
    action_items.sort(key=lambda x: x['financial_impact'], reverse=True)
    
    return action_items[:15]  # Top 15 action items (increased from 10)


def get_payer_performance(practice_data: pd.DataFrame) -> list:
    """Get aggregated payer performance."""
    payer_summary = practice_data.groupby('payer_name').agg({
        'claim_id': 'count',
        'is_denied': 'sum',
        'total_billed_amount': 'sum',
        'total_paid_amount': 'sum',
        'denial_probability': 'mean'
    }).reset_index()
    
    payer_summary.columns = ['payer_name', 'total_claims', 'denied', 'total_billed', 'total_paid', 'avg_denial_prob']
    payer_summary['denial_rate'] = payer_summary['denied'] / payer_summary['total_claims']
    
    # Calculate denied amounts per payer
    denied_by_payer = practice_data[practice_data['is_denied']].groupby('payer_name')['total_billed_amount'].sum().reset_index()
    denied_by_payer.columns = ['payer_name', 'denied_amount']
    payer_summary = payer_summary.merge(denied_by_payer, on='payer_name', how='left')
    payer_summary['denied_amount'] = payer_summary['denied_amount'].fillna(0)
    payer_summary = payer_summary.sort_values('denied_amount', ascending=False)
    
    results = []
    for _, row in payer_summary.iterrows():
        results.append({
            'payer_name': str(row['payer_name']),
            'total_claims': int(row['total_claims']),
            'denied_claims': int(row['denied']),
            'denial_rate': float(row['denial_rate']),
            'total_billed': float(row['total_billed']),
            'total_paid': float(row['total_paid']),
            'denied_amount': float(row['denied_amount']),
            'avg_denial_probability': float(row['avg_denial_prob']),
        })
    
    return results


def get_cpt_performance(practice_data: pd.DataFrame) -> list:
    """Get aggregated CPT code performance."""
    cpt_summary = practice_data[practice_data['primary_cpt_code'].notna() & (practice_data['primary_cpt_code'] != '')].groupby('primary_cpt_code').agg({
        'claim_id': 'count',
        'is_denied': 'sum',
        'total_billed_amount': 'sum',
        'denial_probability': 'mean'
    }).reset_index()
    
    if len(cpt_summary) == 0:
        return []
    
    cpt_summary.columns = ['cpt_code', 'total_claims', 'denied', 'total_billed', 'avg_denial_prob']
    cpt_summary['denial_rate'] = cpt_summary['denied'] / cpt_summary['total_claims']
    
    # Calculate denied amounts per CPT
    denied_by_cpt = practice_data[
        (practice_data['is_denied']) & 
        (practice_data['primary_cpt_code'].notna()) & 
        (practice_data['primary_cpt_code'] != '')
    ].groupby('primary_cpt_code')['total_billed_amount'].sum().reset_index()
    denied_by_cpt.columns = ['cpt_code', 'denied_amount']
    cpt_summary = cpt_summary.merge(denied_by_cpt, on='cpt_code', how='left')
    cpt_summary['denied_amount'] = cpt_summary['denied_amount'].fillna(0)
    cpt_summary = cpt_summary.sort_values('denied_amount', ascending=False)
    
    results = []
    for _, row in cpt_summary.iterrows():
        results.append({
            'cpt_code': str(row['cpt_code']),
            'total_claims': int(row['total_claims']),
            'denied_claims': int(row['denied']),
            'denial_rate': float(row['denial_rate']),
            'total_billed': float(row['total_billed']),
            'denied_amount': float(row['denied_amount']),
            'avg_denial_probability': float(row['avg_denial_prob']),
        })
    
    return results


def get_high_risk_claims(practice_data: pd.DataFrame, limit: int = 20) -> list:
    """Get high-risk claims requiring immediate attention."""
    high_risk_claims = practice_data[practice_data['risk_level'] == 'high'].sort_values('denial_probability', ascending=False)
    
    results = []
    for _, claim in high_risk_claims.head(limit).iterrows():
        results.append({
            'claim_id': str(claim['claim_id']) if pd.notna(claim['claim_id']) else None,
            'payer_name': str(claim['payer_name']) if pd.notna(claim['payer_name']) else 'Unknown',
            'cpt_code': str(claim['primary_cpt_code']) if pd.notna(claim['primary_cpt_code']) else None,
            'denial_probability': float(claim['denial_probability']),
            'billed_amount': float(claim['total_billed_amount']),
            'is_denied': bool(claim['is_denied']) if pd.notna(claim['is_denied']) else False,
        })
    
    return results


async def get_carc_rarc_analysis(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Analyze CARC/RARC codes for a practice.
    
    Args:
        practice_id: Practice GUID
        days_back: Number of days to look back
        repository: Database repository
        
    Returns:
        Dictionary with CARC and RARC code analysis
    """
    from datetime import date, timedelta
    from collections import defaultdict
    
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    
    # Fetch claims for this practice
    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    
    if not claims:
        return {'carc_codes': [], 'rarc_codes': []}
    
    # Fetch denial details for all claims
    carc_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0.0, 'claims': set()})
    rarc_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0.0, 'claims': set()})
    
    for claim in claims:
        denial_details = await repository.get_denial_details(claim.claim_id)
        
        for detail in denial_details:
            if detail.carc_code:
                carc_stats[detail.carc_code]['count'] += 1
                carc_stats[detail.carc_code]['claims'].add(claim.claim_id)
                if detail.adjustment_amount:
                    carc_stats[detail.carc_code]['total_amount'] += float(detail.adjustment_amount)
            
            if detail.rarc_code:
                rarc_stats[detail.rarc_code]['count'] += 1
                rarc_stats[detail.rarc_code]['claims'].add(claim.claim_id)
                if detail.adjustment_amount:
                    rarc_stats[detail.rarc_code]['total_amount'] += float(detail.adjustment_amount)
    
    # Convert to list format
    carc_results = []
    for code, stats in sorted(carc_stats.items(), key=lambda x: x[1]['total_amount'], reverse=True):
        carc_results.append({
            'carc_code': int(code),
            'occurrence_count': stats['count'],
            'affected_claims': len(stats['claims']),
            'total_adjustment_amount': float(stats['total_amount']),
            'description': _get_carc_description(code),
        })
    
    rarc_results = []
    for code, stats in sorted(rarc_stats.items(), key=lambda x: x[1]['total_amount'], reverse=True):
        rarc_results.append({
            'rarc_code': str(code),
            'occurrence_count': stats['count'],
            'affected_claims': len(stats['claims']),
            'total_adjustment_amount': float(stats['total_amount']),
        })
    
    return {
        'carc_codes': carc_results,
        'rarc_codes': rarc_results,
    }


def _get_carc_description(carc_code: int) -> str:
    """Get description for a CARC code."""
    from src.utils.constants import COMMON_CARC_CODES
    
    if carc_code in COMMON_CARC_CODES:
        return COMMON_CARC_CODES[carc_code]
    
    # Map common codes to categories
    if carc_code in [1, 2, 3]:
        return "Patient Responsibility (Deductible/Coinsurance/Copay)"
    elif carc_code in [4, 5, 6, 11, 16, 18]:
        return "Coding Error"
    elif carc_code in [50, 54, 55, 56, 57, 58, 59]:
        return "Medical Necessity"
    elif carc_code in [22, 23, 24, 25, 26]:
        return "Coordination of Benefits"
    elif carc_code in [29, 95]:
        return "Timely Filing"
    else:
        return f"CARC {carc_code}"


async def get_cpt_carc_correlation(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Analyze correlation between CPT codes and CARC/RARC codes.
    
    This shows which procedure codes are most commonly associated with
    which denial reasons, helping identify root causes.
    
    Args:
        practice_id: Practice GUID
        days_back: Number of days to look back
        repository: Database repository
        
    Returns:
        Dictionary with CPT-CARC and CPT-RARC correlations
    """
    from datetime import date, timedelta
    from collections import defaultdict
    
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    
    # Fetch claims for this practice
    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    
    if not claims:
        return {'cpt_carc': [], 'cpt_rarc': []}
    
    # Track CPT-CARC and CPT-RARC combinations
    cpt_carc_stats = defaultdict(lambda: {
        'count': 0,
        'total_amount': 0.0,
        'claims': set(),
        'cpt_code': None,
        'carc_code': None,
    })
    cpt_rarc_stats = defaultdict(lambda: {
        'count': 0,
        'total_amount': 0.0,
        'claims': set(),
        'cpt_code': None,
        'rarc_code': None,
    })
    
    # Process each claim
    for claim in claims:
        # Get line items for this claim
        line_items = await repository.get_claim_line_items(claim.claim_id)
        
        # Create a map of line_item_id -> CPT code
        line_item_cpt_map = {}
        for line_item in line_items:
            cpt_code = line_item.cpt_code
            # Handle format like "HC:92507:GN" - extract middle part
            if cpt_code and ":" in cpt_code:
                parts = cpt_code.split(":")
                cpt_code = parts[1] if len(parts) > 1 else cpt_code
            line_item_cpt_map[line_item.line_item_id] = cpt_code
        
        # Get denial details for this claim
        denial_details = await repository.get_denial_details(claim.claim_id)
        
        # Match denial details to line items (and thus CPT codes)
        for detail in denial_details:
            # Try to find the CPT code for this denial detail
            cpt_code = None
            if detail.line_item_id:
                cpt_code = line_item_cpt_map.get(detail.line_item_id)
            
            # If no line_item_id match, use primary CPT from first line item
            if not cpt_code and line_items:
                primary_cpt = line_items[0].cpt_code
                if primary_cpt and ":" in primary_cpt:
                    parts = primary_cpt.split(":")
                    primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
                cpt_code = primary_cpt
            
            # Track CARC code correlations
            if detail.carc_code and cpt_code:
                key = (cpt_code, detail.carc_code)
                cpt_carc_stats[key]['count'] += 1
                cpt_carc_stats[key]['claims'].add(claim.claim_id)
                cpt_carc_stats[key]['cpt_code'] = cpt_code
                cpt_carc_stats[key]['carc_code'] = detail.carc_code
                if detail.adjustment_amount:
                    cpt_carc_stats[key]['total_amount'] += float(detail.adjustment_amount)
            
            # Track RARC code correlations
            if detail.rarc_code and cpt_code:
                key = (cpt_code, detail.rarc_code)
                cpt_rarc_stats[key]['count'] += 1
                cpt_rarc_stats[key]['claims'].add(claim.claim_id)
                cpt_rarc_stats[key]['cpt_code'] = cpt_code
                cpt_rarc_stats[key]['rarc_code'] = detail.rarc_code
                if detail.adjustment_amount:
                    cpt_rarc_stats[key]['total_amount'] += float(detail.adjustment_amount)
    
    # Convert to list format, sorted by financial impact
    cpt_carc_results = []
    for (cpt_code, carc_code), stats in sorted(
        cpt_carc_stats.items(),
        key=lambda x: x[1]['total_amount'],
        reverse=True
    ):
        cpt_carc_results.append({
            'cpt_code': str(cpt_code),
            'carc_code': int(carc_code),
            'occurrence_count': stats['count'],
            'affected_claims': len(stats['claims']),
            'total_adjustment_amount': float(stats['total_amount']),
            'carc_description': _get_carc_description(carc_code),
        })
    
    cpt_rarc_results = []
    for (cpt_code, rarc_code), stats in sorted(
        cpt_rarc_stats.items(),
        key=lambda x: x[1]['total_amount'],
        reverse=True
    ):
        cpt_rarc_results.append({
            'cpt_code': str(cpt_code),
            'rarc_code': str(rarc_code),
            'occurrence_count': stats['count'],
            'affected_claims': len(stats['claims']),
            'total_adjustment_amount': float(stats['total_amount']),
        })
    
    return {
        'cpt_carc': cpt_carc_results,
        'cpt_rarc': cpt_rarc_results,
    }


async def get_rejection_pattern_analysis(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Analyze rejection patterns for a practice.
    
    Identifies which CPT codes are associated with which rejection issues
    (missing fields, invalid data, etc.).
    
    Args:
        practice_id: Practice GUID
        days_back: Number of days to look back
        repository: Database repository
        
    Returns:
        Dictionary with rejection pattern analysis
    """
    from datetime import date, timedelta
    from collections import defaultdict
    from src.data_access.models import ClaimStatus
    
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    
    # Fetch claims for this practice
    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    
    if not claims:
        return {'rejection_patterns': []}
    
    # Track rejection patterns by CPT code
    cpt_rejection_patterns = defaultdict(lambda: {
        'cpt_code': None,
        'missing_patient_id': 0,
        'missing_provider_id': 0,
        'missing_service_date': 0,
        'missing_submitted_date': 0,
        'invalid_date_order': 0,
        'missing_cpt_in_line_items': 0,
        'invalid_cpt_count': 0,
        'missing_billed_amount': 0,
        'missing_line_items': 0,
        'total_rejections': 0,
        'total_claims': 0,
        'rejection_rate': 0.0,
    })
    
    # Process each claim
    # Identify claims that are rejected OR should be rejected based on content issues
    for claim in claims:
        # Get line items for this claim
        line_items = await repository.get_claim_line_items(claim.claim_id)
        
        # Extract primary CPT
        primary_cpt = None
        if line_items:
            primary_cpt = line_items[0].cpt_code
            if primary_cpt and ":" in primary_cpt:
                parts = primary_cpt.split(":")
                primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
        
        if not primary_cpt:
            continue
        
        # Check if this claim is actually rejected OR has rejection-indicating issues
        is_rejected = (claim.status == ClaimStatus.REJECTED)
        
        # Also identify claims that should be rejected based on content issues
        # (even if status doesn't explicitly say rejected)
        has_rejection_issues = False
        rejection_issues = {
            'missing_patient_id': False,
            'missing_provider_id': False,
            'missing_service_date': False,
            'missing_submitted_date': False,
            'invalid_date_order': False,
            'missing_cpt_in_line_items': False,
            'invalid_cpt_count': False,
            'missing_billed_amount': False,
            'missing_line_items': False,
        }
        
        # Check for missing fields
        if not claim.patient_id or claim.patient_id == "":
            has_rejection_issues = True
            rejection_issues['missing_patient_id'] = True
        if not claim.provider_id or claim.provider_id == "":
            has_rejection_issues = True
            rejection_issues['missing_provider_id'] = True
        if not claim.service_date_from:
            has_rejection_issues = True
            rejection_issues['missing_service_date'] = True
        if not claim.submitted_date:
            # Missing submitted_date is a common rejection reason
            # Claims need to have a submission date to be processed
            has_rejection_issues = True
            rejection_issues['missing_submitted_date'] = True
        
        # Check for missing line items
        if not line_items or len(line_items) == 0:
            has_rejection_issues = True
            rejection_issues['missing_line_items'] = True
        
        # Check for invalid date order
        if claim.service_date_from and claim.submitted_date:
            if claim.submitted_date < claim.service_date_from:
                has_rejection_issues = True
                rejection_issues['invalid_date_order'] = True
        
        # Check for missing CPT codes in line items
        missing_cpt_count = sum(1 for item in line_items if not item.cpt_code or item.cpt_code == "")
        if missing_cpt_count > 0:
            has_rejection_issues = True
            rejection_issues['missing_cpt_in_line_items'] = True
        
        # Check for invalid CPT/HCPCS codes
        # Valid formats:
        # - CPT codes: 5 digits (e.g., "97110") or 4 digits (e.g., "9921")
        # - HCPCS Level II codes: 1 letter + 4 digits (e.g., "G0283", "A1234")
        # - Proprietary lab codes: 4 digits + 1 letter (e.g., "0433U", "0174U")
        invalid_cpt_count = 0
        for item in line_items:
            if item.cpt_code:
                cpt = item.cpt_code
                if ":" in cpt:
                    parts = cpt.split(":")
                    cpt = parts[1] if len(parts) > 1 else cpt
                
                # Check if CPT/HCPCS code is valid
                is_valid = False
                if len(cpt) >= 5:
                    # Check for numeric CPT code (5 digits)
                    if cpt[:5].isdigit():
                        is_valid = True
                    # Check for HCPCS Level II code (1 letter + 4 digits, e.g., "G0283")
                    elif len(cpt) == 5 and cpt[0].isalpha() and cpt[1:5].isdigit():
                        is_valid = True
                    # Check for proprietary lab code (4 digits + 1 letter, e.g., "0433U")
                    elif len(cpt) == 5 and cpt[:4].isdigit() and cpt[4].isalpha():
                        is_valid = True
                elif len(cpt) == 4 and cpt.isdigit():
                    # 4-digit CPT codes are also valid
                    is_valid = True
                
                if not is_valid:
                    invalid_cpt_count += 1
        if invalid_cpt_count > 0:
            has_rejection_issues = True
            rejection_issues['invalid_cpt_count'] = True
        
        # Check for missing billed amount
        if not claim.total_billed_amount or float(claim.total_billed_amount) == 0:
            has_rejection_issues = True
            rejection_issues['missing_billed_amount'] = True
        
        # Only process if actually rejected
        # We only analyze actual rejections to identify patterns, not potential rejections
        if not is_rejected:
            continue
        
        # Extract primary CPT (we already have line_items from above)
        primary_cpt = None
        if line_items:
            primary_cpt = line_items[0].cpt_code
            if primary_cpt and ":" in primary_cpt:
                parts = primary_cpt.split(":")
                primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
        
        if not primary_cpt:
            continue
        
        # Initialize if first time seeing this CPT
        if cpt_rejection_patterns[primary_cpt]['cpt_code'] is None:
            cpt_rejection_patterns[primary_cpt]['cpt_code'] = primary_cpt
        
        # Count as rejection (this is an actual rejection)
        cpt_rejection_patterns[primary_cpt]['total_rejections'] += 1
        
        # Track specific rejection issues
        if rejection_issues['missing_patient_id']:
            cpt_rejection_patterns[primary_cpt]['missing_patient_id'] += 1
        if rejection_issues['missing_provider_id']:
            cpt_rejection_patterns[primary_cpt]['missing_provider_id'] += 1
        if rejection_issues['missing_service_date']:
            cpt_rejection_patterns[primary_cpt]['missing_service_date'] += 1
        if rejection_issues['missing_submitted_date']:
            cpt_rejection_patterns[primary_cpt]['missing_submitted_date'] += 1
        if rejection_issues['invalid_date_order']:
            cpt_rejection_patterns[primary_cpt]['invalid_date_order'] += 1
        if rejection_issues['missing_cpt_in_line_items']:
            cpt_rejection_patterns[primary_cpt]['missing_cpt_in_line_items'] += missing_cpt_count
        if rejection_issues['invalid_cpt_count']:
            cpt_rejection_patterns[primary_cpt]['invalid_cpt_count'] += invalid_cpt_count
        if rejection_issues['missing_billed_amount']:
            cpt_rejection_patterns[primary_cpt]['missing_billed_amount'] += 1
        if rejection_issues['missing_line_items']:
            cpt_rejection_patterns[primary_cpt]['missing_line_items'] += 1
    
    # Count total claims per CPT (for rejection rate calculation)
    cpt_total_claims = defaultdict(int)
    for claim in claims:
        line_items = await repository.get_claim_line_items(claim.claim_id)
        if line_items:
            primary_cpt = line_items[0].cpt_code
            if primary_cpt and ":" in primary_cpt:
                parts = primary_cpt.split(":")
                primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
            if primary_cpt:
                cpt_total_claims[primary_cpt] += 1
    
    # Calculate rejection rates and create results
    results = []
    for cpt_code, patterns in cpt_rejection_patterns.items():
        total_claims_for_cpt = cpt_total_claims.get(cpt_code, 0)
        rejection_rate = patterns['total_rejections'] / total_claims_for_cpt if total_claims_for_cpt > 0 else 0.0
        
        # Calculate rejection risk score
        risk_score = (
            patterns['missing_patient_id'] * 3 +
            patterns['missing_provider_id'] * 3 +
            patterns['missing_service_date'] * 3 +
            patterns['missing_submitted_date'] * 4 +  # High weight - critical for submission
            patterns['invalid_date_order'] * 3 +
            patterns['missing_cpt_in_line_items'] * 2 +
            patterns['invalid_cpt_count'] * 2 +
            patterns['missing_billed_amount'] * 2 +
            patterns['missing_line_items'] * 5  # Very high weight - claims need line items
        )
        
        results.append({
            'cpt_code': cpt_code,
            'total_rejections': patterns['total_rejections'],
            'total_claims': total_claims_for_cpt,
            'rejection_rate': rejection_rate,
            'missing_patient_id': patterns['missing_patient_id'],
            'missing_provider_id': patterns['missing_provider_id'],
            'missing_service_date': patterns['missing_service_date'],
            'missing_submitted_date': patterns['missing_submitted_date'],
            'invalid_date_order': patterns['invalid_date_order'],
            'missing_cpt_in_line_items': patterns['missing_cpt_in_line_items'],
            'invalid_cpt_count': patterns['invalid_cpt_count'],
            'missing_billed_amount': patterns['missing_billed_amount'],
            'missing_line_items': patterns['missing_line_items'],
            'rejection_risk_score': risk_score,
        })
    
    # Sort by rejection risk score (highest first)
    results.sort(key=lambda x: x['rejection_risk_score'], reverse=True)
    
    return {'rejection_patterns': results}


"""Temporal feature extraction.

Extracts time-based features from claim dates.
"""

from datetime import date, datetime, timedelta
from typing import Optional
import math
import structlog

logger = structlog.get_logger()


def extract_temporal_features(
    service_date: Optional[date],
    submitted_date: Optional[date],
    reference_date: Optional[date] = None
) -> dict:
    """Extract temporal features from service and submitted dates.
    
    Args:
        service_date: Date of service
        submitted_date: Date claim was submitted
        reference_date: Reference date for calculations (defaults to today)
        
    Returns:
        Dictionary of temporal feature names and values
    """
    features = {}
    
    if reference_date is None:
        reference_date = date.today()
    
    # Service date features
    if service_date:
        features["service_date"] = service_date
        features["day_of_week_service"] = service_date.weekday()  # 0=Monday, 6=Sunday
        features["day_of_month_service"] = service_date.day
        features["month_of_service"] = service_date.month
        features["quarter_of_service"] = (service_date.month - 1) // 3 + 1
        features["year_of_service"] = service_date.year
        
        # Cyclical encoding for month (sin/cos)
        month_rad = 2 * math.pi * service_date.month / 12
        features["month_sin"] = math.sin(month_rad)
        features["month_cos"] = math.cos(month_rad)
        
        # Cyclical encoding for day of week
        dow_rad = 2 * math.pi * service_date.weekday() / 7
        features["day_of_week_sin"] = math.sin(dow_rad)
        features["day_of_week_cos"] = math.cos(dow_rad)
        
        # Days since service
        days_since_service = (reference_date - service_date).days
        features["days_since_service"] = days_since_service
    else:
        features["service_date"] = None
        features["day_of_week_service"] = None
        features["month_of_service"] = None
        features["quarter_of_service"] = None
        features["days_since_service"] = None
    
    # Submitted date features
    if submitted_date:
        features["submitted_date"] = submitted_date
        features["day_of_week_submitted"] = submitted_date.weekday()
        features["month_of_submitted"] = submitted_date.month
        
        # Days to filing deadline (typically 90 days from service)
        if service_date:
            days_to_deadline = 90 - (submitted_date - service_date).days
            features["days_to_filing_deadline"] = days_to_deadline
            features["is_near_deadline"] = days_to_deadline < 7
            features["is_past_deadline"] = days_to_deadline < 0
        else:
            features["days_to_filing_deadline"] = None
            features["is_near_deadline"] = False
            features["is_past_deadline"] = False
        
        # Days between service and submission
        if service_date:
            days_between = (submitted_date - service_date).days
            features["days_service_to_submission"] = days_between
            features["is_same_day_submission"] = days_between == 0
            features["is_delayed_submission"] = days_between > 30
        else:
            features["days_service_to_submission"] = None
            features["is_same_day_submission"] = False
            features["is_delayed_submission"] = False
    else:
        features["submitted_date"] = None
        features["day_of_week_submitted"] = None
        features["days_to_filing_deadline"] = None
        features["days_service_to_submission"] = None
    
    # Is weekend service
    if service_date:
        features["is_weekend_service"] = service_date.weekday() >= 5
    else:
        features["is_weekend_service"] = False
    
    # Is end of month/quarter/year
    if service_date:
        features["is_month_end"] = service_date.day >= 28
        features["is_quarter_end"] = service_date.month in [3, 6, 9, 12] and service_date.day >= 28
        features["is_year_end"] = service_date.month == 12 and service_date.day >= 28
    else:
        features["is_month_end"] = False
        features["is_quarter_end"] = False
        features["is_year_end"] = False
    
    return features


def extract_time_since_features(
    last_claim_date: Optional[date],
    last_denial_date: Optional[date],
    reference_date: Optional[date] = None
) -> dict:
    """Extract features about time since last events.
    
    Args:
        last_claim_date: Date of last claim for this patient/practice
        last_denial_date: Date of last denial for this patient/practice
        reference_date: Reference date for calculations
        
    Returns:
        Dictionary of time-since features
    """
    features = {}
    
    if reference_date is None:
        reference_date = date.today()
    
    # Days since last claim
    if last_claim_date:
        days_since = (reference_date - last_claim_date).days
        features["days_since_last_claim"] = days_since
        features["has_recent_claim"] = days_since < 30
    else:
        features["days_since_last_claim"] = None
        features["has_recent_claim"] = False
    
    # Days since last denial
    if last_denial_date:
        days_since = (reference_date - last_denial_date).days
        features["days_since_last_denial"] = days_since
        features["has_recent_denial"] = days_since < 90
    else:
        features["days_since_last_denial"] = None
        features["has_recent_denial"] = False
    
    return features

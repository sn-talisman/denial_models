"""Code normalization for CPT, ICD-10, and modifiers.

Standardizes procedure codes, diagnosis codes, and modifiers
for consistent feature engineering.
"""

from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


def normalize_cpt_code(cpt_code: Optional[str]) -> Optional[str]:
    """Normalize CPT code format.
    
    Args:
        cpt_code: CPT code (may include dashes, spaces, etc.)
        
    Returns:
        Normalized CPT code (5 digits, no dashes)
    """
    if not cpt_code:
        return None
    
    # Remove dashes, spaces, and convert to uppercase
    normalized = cpt_code.replace("-", "").replace(" ", "").upper().strip()
    
    # Extract numeric portion (first 5 digits)
    digits = "".join(c for c in normalized if c.isdigit())
    if len(digits) >= 5:
        return digits[:5]
    
    return normalized if normalized else None


def normalize_icd10_code(icd10_code: Optional[str]) -> Optional[str]:
    """Normalize ICD-10 code format.
    
    Args:
        icd10_code: ICD-10 code (may include dots, spaces, etc.)
        
    Returns:
        Normalized ICD-10 code (standard format: A00.0)
    """
    if not icd10_code:
        return None
    
    # Remove spaces and convert to uppercase
    normalized = icd10_code.replace(" ", "").upper().strip()
    
    # Ensure proper format (letter + digits + optional dot + optional digits)
    # Example: E11.9, I10, Z00.00
    if len(normalized) >= 3:
        # Insert dot if missing and code is long enough
        if "." not in normalized and len(normalized) > 3:
            normalized = normalized[:3] + "." + normalized[3:]
        
        return normalized
    
    return normalized if normalized else None


def normalize_modifier(modifier: Optional[str]) -> Optional[str]:
    """Normalize modifier code.
    
    Args:
        modifier: Modifier code (may include spaces, etc.)
        
    Returns:
        Normalized modifier (2 characters, uppercase)
    """
    if not modifier:
        return None
    
    # Remove spaces, convert to uppercase, take first 2 characters
    normalized = modifier.replace(" ", "").upper().strip()
    
    if len(normalized) >= 2:
        return normalized[:2]
    
    return normalized if normalized else None


def normalize_place_of_service(pos_code: Optional[str]) -> Optional[str]:
    """Normalize place of service code.
    
    Args:
        pos_code: Place of service code
        
    Returns:
        Normalized POS code (2 digits)
    """
    if not pos_code:
        return None
    
    # Extract numeric portion
    digits = "".join(c for c in str(pos_code) if c.isdigit())
    
    if len(digits) >= 2:
        return digits[:2]
    
    return digits if digits else None


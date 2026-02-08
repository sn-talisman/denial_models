"""LLM-based denial reason classifier for ambiguous cases.

This module provides LLM-powered classification when rule-based
taxonomy matching is insufficient.
"""

from typing import Optional
import structlog

from src.llm.llm_client import LLMClient

logger = structlog.get_logger(__name__)


def classify_denial_with_llm(
    denial_text: str,
    carc_code: Optional[int] = None,
    rarc_code: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
) -> dict[str, str | float]:
    """Classify denial reason using LLM.
    
    Args:
        denial_text: Free-text denial reason
        carc_code: Optional CARC code
        rarc_code: Optional RARC code
        llm_client: Optional LLM client (creates one if None)
        
    Returns:
        Dictionary with 'category' and 'confidence' keys
    """
    if llm_client is None:
        llm_client = LLMClient()
    
    try:
        result = llm_client.classify_denial_reason(
            denial_text=denial_text,
            carc_code=carc_code,
            rarc_code=rarc_code,
        )
        logger.info("LLM classification completed", category=result.get("category"))
        return result
    except Exception as e:
        logger.error("LLM classification failed", error=str(e))
        return {"category": "other", "confidence": 0.0}


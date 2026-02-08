"""Denial taxonomy normalization.

Maps CARC codes, RARC codes, and free-text denial reasons to
standardized denial categories using rule-based matching and
LLM fallback for ambiguous cases.
"""

from pathlib import Path
from typing import Optional
import yaml
import structlog

from src.llm.llm_client import LLMClient

logger = structlog.get_logger(__name__)


class DenialTaxonomyNormalizer:
    """Normalizes denial reasons to standardized taxonomy categories."""
    
    def __init__(self, taxonomy_path: Optional[Path] = None, llm_client: Optional[LLMClient] = None):
        """Initialize taxonomy normalizer.
        
        Args:
            taxonomy_path: Path to denial_taxonomy.yaml. Defaults to config/denial_taxonomy.yaml
            llm_client: Optional LLM client for ambiguous cases. If None, creates one.
        """
        if taxonomy_path is None:
            taxonomy_path = Path(__file__).parent.parent.parent.parent / "config" / "denial_taxonomy.yaml"
        
        self.taxonomy_path = taxonomy_path
        self.taxonomy = self._load_taxonomy()
        self.llm_client = llm_client or LLMClient()
        
        logger.info("Denial taxonomy normalizer initialized", categories=len(self.taxonomy["categories"]))
    
    def _load_taxonomy(self) -> dict:
        """Load taxonomy configuration from YAML."""
        try:
            with open(self.taxonomy_path, "r") as f:
                taxonomy = yaml.safe_load(f)
            logger.info("Loaded denial taxonomy", path=str(self.taxonomy_path))
            return taxonomy
        except Exception as e:
            logger.error("Failed to load denial taxonomy", error=str(e), path=str(self.taxonomy_path))
            raise
    
    def normalize_by_carc(self, carc_code: Optional[int]) -> Optional[str]:
        """Normalize denial category by CARC code.
        
        Args:
            carc_code: CARC code
            
        Returns:
            Category name if found, None otherwise
        """
        if carc_code is None:
            return None
        
        for category, config in self.taxonomy["categories"].items():
            if carc_code in config.get("carc_codes", []):
                logger.debug("Matched CARC code to category", carc_code=carc_code, category=category)
                return category
        
        logger.debug("No category match for CARC code", carc_code=carc_code)
        return None
    
    def normalize_by_keywords(self, denial_text: Optional[str]) -> Optional[str]:
        """Normalize denial category by keyword matching.
        
        Args:
            denial_text: Free-text denial reason
            
        Returns:
            Category name if keywords match, None otherwise
        """
        if not denial_text:
            return None
        
        denial_text_lower = denial_text.lower()
        best_match = None
        best_score = 0
        
        for category, config in self.taxonomy["categories"].items():
            keywords = config.get("keywords", [])
            score = sum(1 for keyword in keywords if keyword.lower() in denial_text_lower)
            
            if score > best_score:
                best_score = score
                best_match = category
        
        if best_match and best_score > 0:
            logger.debug(
                "Matched keywords to category",
                category=best_match,
                score=best_score,
                text_preview=denial_text[:50],
            )
            return best_match
        
        return None
    
    def normalize(
        self,
        carc_code: Optional[int] = None,
        rarc_code: Optional[str] = None,
        denial_text: Optional[str] = None,
        use_llm_fallback: bool = True,
    ) -> tuple[str, float]:
        """Normalize denial reason to category with confidence score.
        
        Args:
            carc_code: Optional CARC code
            rarc_code: Optional RARC code
            denial_text: Optional free-text denial reason
            use_llm_fallback: Whether to use LLM for ambiguous cases
            
        Returns:
            Tuple of (category_name, confidence_score)
        """
        # Try CARC code first (most reliable)
        if carc_code is not None:
            category = self.normalize_by_carc(carc_code)
            if category:
                return (category, 0.95)
        
        # Try keyword matching
        if denial_text:
            category = self.normalize_by_keywords(denial_text)
            if category:
                return (category, 0.80)
        
        # Use LLM fallback if enabled
        if use_llm_fallback and denial_text:
            try:
                result = self.llm_client.classify_denial_reason(
                    denial_text=denial_text,
                    carc_code=carc_code,
                    rarc_code=rarc_code,
                )
                category = result.get("category", "other")
                confidence = result.get("confidence", 0.5)
                logger.info("Used LLM for denial classification", category=category, confidence=confidence)
                return (category, confidence)
            except Exception as e:
                logger.warning("LLM classification failed, using 'other'", error=str(e))
        
        # Default to "other"
        return ("other", 0.3)


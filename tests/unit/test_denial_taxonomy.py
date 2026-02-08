"""Unit tests for denial taxonomy normalization."""

import pytest
from pathlib import Path

from src.pipelines.normalization.denial_taxonomy import DenialTaxonomyNormalizer


def test_taxonomy_normalizer_init():
    """Test taxonomy normalizer initialization."""
    normalizer = DenialTaxonomyNormalizer()
    assert normalizer.taxonomy is not None
    assert "categories" in normalizer.taxonomy


def test_normalize_by_carc():
    """Test CARC code normalization."""
    normalizer = DenialTaxonomyNormalizer()
    
    # Test known CARC code (1 = Deductible, should map to eligibility_coverage)
    category, confidence = normalizer.normalize(carc_code=1)
    assert category == "eligibility_coverage"
    assert confidence > 0.5
    
    # Test unknown CARC code
    category, confidence = normalizer.normalize(carc_code=99999)
    assert category == "other" or confidence < 0.5


def test_normalize_by_keywords():
    """Test keyword-based normalization."""
    normalizer = DenialTaxonomyNormalizer()
    
    # Test eligibility keyword
    category, confidence = normalizer.normalize(denial_text="Patient coverage terminated")
    assert "eligibility" in category.lower() or confidence > 0.5
    
    # Test authorization keyword
    category, confidence = normalizer.normalize(denial_text="Prior authorization required")
    assert "authorization" in category.lower() or confidence > 0.5


def test_normalize_fallback():
    """Test normalization fallback to 'other'."""
    normalizer = DenialTaxonomyNormalizer()
    
    # Test with no matching criteria
    category, confidence = normalizer.normalize(
        carc_code=None,
        denial_text="Unknown reason",
        use_llm_fallback=False,
    )
    assert category == "other"
    assert confidence < 0.5


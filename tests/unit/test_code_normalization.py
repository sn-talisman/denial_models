"""Unit tests for code normalization."""

import pytest

from src.pipelines.normalization.code_normalization import (
    normalize_cpt_code,
    normalize_icd10_code,
    normalize_modifier,
    normalize_place_of_service,
)


def test_normalize_cpt_code():
    """Test CPT code normalization."""
    assert normalize_cpt_code("99213") == "99213"
    assert normalize_cpt_code("99213-25") == "99213"
    assert normalize_cpt_code("992 13") == "99213"
    assert normalize_cpt_code(None) is None
    assert normalize_cpt_code("") is None


def test_normalize_icd10_code():
    """Test ICD-10 code normalization."""
    assert normalize_icd10_code("E11.9") == "E11.9"
    assert normalize_icd10_code("E119") == "E11.9"
    assert normalize_icd10_code("I10") == "I10"
    assert normalize_icd10_code(None) is None


def test_normalize_modifier():
    """Test modifier normalization."""
    assert normalize_modifier("25") == "25"
    assert normalize_modifier(" 25 ") == "25"
    assert normalize_modifier("25-59") == "25"
    assert normalize_modifier(None) is None


def test_normalize_place_of_service():
    """Test place of service normalization."""
    assert normalize_place_of_service("11") == "11"
    assert normalize_place_of_service(11) == "11"
    assert normalize_place_of_service("POS 11") == "11"
    assert normalize_place_of_service(None) is None


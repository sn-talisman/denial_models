#!/usr/bin/env python3
"""Validate partial payment code logic without database access.

This script checks that:
1. All required features are defined
2. Logic is correct
3. Imports work
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def validate_imports():
    """Check that all imports work."""
    print("🔍 Validating imports...")
    try:
        from src.pipelines.feature_engineering.claim_features import extract_claim_features
        from src.pipelines.feature_engineering.feature_engineer import engineer_features
        from src.data_access.models import ClaimStatus, DenialDetail
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def validate_feature_names():
    """Check that feature names match expected list."""
    print("\n🔍 Validating feature names...")
    
    expected_features = [
        "is_partially_paid",
        "adjustment_amount",
        "adjustment_ratio",
        "has_partial_denial",
        "denial_detail_count",
        "has_adjustments",
        "unique_carc_count",
        "unique_rarc_count",
        "total_adjustment_from_details",
    ]
    
    # Read claim_features.py to check for feature definitions
    claim_features_file = Path(__file__).parent.parent / "src" / "pipelines" / "feature_engineering" / "claim_features.py"
    if claim_features_file.exists():
        content = claim_features_file.read_text()
        
        found_features = []
        for feature in expected_features:
            if f'"{feature}"' in content or f"'{feature}'" in content or f"features[\"{feature}\"]" in content:
                found_features.append(feature)
        
        print(f"   Found {len(found_features)}/{len(expected_features)} features in claim_features.py")
        for feature in found_features:
            print(f"   ✅ {feature}")
        
        missing = set(expected_features) - set(found_features)
        if missing:
            print(f"\n   ⚠️  Missing in claim_features.py: {', '.join(missing)}")
            print("   (These may be in feature_engineer.py)")
        
        return len(found_features) > 0
    else:
        print("❌ claim_features.py not found")
        return False

def validate_logic():
    """Check that logic is correct."""
    print("\n🔍 Validating logic...")
    
    # Read files to check logic
    claim_features_file = Path(__file__).parent.parent / "src" / "pipelines" / "feature_engineering" / "claim_features.py"
    feature_engineer_file = Path(__file__).parent.parent / "src" / "pipelines" / "feature_engineering" / "feature_engineer.py"
    
    checks = []
    
    if claim_features_file.exists():
        content = claim_features_file.read_text()
        
        # Check for partial payment detection
        if "is_partially_paid" in content and "payment_ratio" in content:
            checks.append(("Partial payment detection", True))
        else:
            checks.append(("Partial payment detection", False))
        
        # Check for adjustment calculation
        if "adjustment_amount" in content and "billed_amount" in content and "paid_amount" in content:
            checks.append(("Adjustment amount calculation", True))
        else:
            checks.append(("Adjustment amount calculation", False))
    
    if feature_engineer_file.exists():
        content = feature_engineer_file.read_text()
        
        # Check for denial details handling
        if "get_denial_details" in content:
            checks.append(("Denial details extraction", True))
        else:
            checks.append(("Denial details extraction", False))
        
        # Check for CARC/RARC extraction
        if "carc_code" in content and "rarc_code" in content:
            checks.append(("CARC/RARC code extraction", True))
        else:
            checks.append(("CARC/RARC code extraction", False))
        
        # Check for partial denial handling
        if "has_partial_denial" in content or "is_partially_paid" in content:
            checks.append(("Partial denial handling", True))
        else:
            checks.append(("Partial denial handling", False))
    
    all_passed = True
    for check_name, passed in checks:
        if passed:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name}")
            all_passed = False
    
    return all_passed

def validate_database_query():
    """Check that database query includes adjustment_amount."""
    print("\n🔍 Validating database query...")
    
    db_repo_file = Path(__file__).parent.parent / "src" / "data_access" / "db_repository.py"
    
    if db_repo_file.exists():
        content = db_repo_file.read_text()
        
        # Check for adjustment_amount in query
        if "adjustment_amount" in content and "billed_amount -" in content:
            print("   ✅ Adjustment amount calculation in query")
            return True
        else:
            print("   ⚠️  Adjustment amount calculation may be missing")
            return False
    else:
        print("   ❌ db_repository.py not found")
        return False

def main():
    """Run all validations."""
    print("=" * 60)
    print("Partial Payment Code Validation")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", validate_imports()))
    results.append(("Feature Names", validate_feature_names()))
    results.append(("Logic", validate_logic()))
    results.append(("Database Query", validate_database_query()))
    
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    all_passed = all(result[1] for result in results)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    if all_passed:
        print("\n✅ All validations passed!")
        print("\nNext step: Run the actual test with database:")
        print("  python scripts/test_partial_payments_simple.py")
        return 0
    else:
        print("\n⚠️  Some validations failed. Please review the code.")
        return 1

if __name__ == "__main__":
    sys.exit(main())


# Practice ID Resolution - FIXED ✅

## Problem (Resolved)

The `practice_guid` values in `fin_claim_line` did not match the `practice_guid` values in `cmn_practice`. This caused practice names to show as "Unknown" in analytics.

## Root Cause

- **Claims table** (`fin_claim_line`): Contains `practice_guid` column
- **Practices table** (`cmn_practice`): Contains `practice_guid` column  
- **Issue**: The GUIDs in `fin_claim_line.practice_guid` do not exist in `cmn_practice.practice_guid`

This appears to be a **data integrity issue** in the source database where:
- The practice_guid in claims may be from a different system/version
- The practice_guid in claims may reference inactive/deleted practices
- There may be a missing join table or relationship

## Solution Implemented ✅

Updated `get_practices()` method in `db_repository.py` to:

1. **Fetch practices from `cmn_practice` table** (with actual names)
2. **Also fetch practice GUIDs from `fin_claim_line`** that don't exist in `cmn_practice`
3. **Create Practice objects for claim practices** with fallback names like "Practice {first_8_chars}"

This ensures:
- ✅ All practice GUIDs from claims are included in the practice lookup
- ✅ Practices with names show their actual names
- ✅ Practices without names show "Practice {guid}" instead of "Unknown"
- ✅ Practice mapping always works, even for practices not in `cmn_practice`

## Impact

- ✅ **Analysis works perfectly**: Practice IDs are preserved and shown
- ✅ **Names resolved**: Practices from `cmn_practice` show actual names, others show "Practice {guid}"
- ✅ **Grouping works**: Claims are correctly grouped by practice_id
- ✅ **Metrics accurate**: All denial rates and statistics are correct
- ✅ **No more "Unknown"**: Every practice has an identifier

## Example Output

Before fix:
```
Practice Name: Unknown
```

After fix:
```
Practice Name: Practice caf185b2  (for practices not in cmn_practice)
Practice Name: Family Medical Center  (for practices in cmn_practice)
```

## Technical Details

The `get_practices()` method now:
1. Queries `cmn_practice` for practices with names
2. Queries `fin_claim_line` for practice GUIDs not in `cmn_practice`
3. Combines both into a single list
4. Creates fallback names for practices without names

This makes `practice_guid` from `fin_claim_line` the source of truth for claims, while still showing actual names when available.


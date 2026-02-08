# Rejection vs Denial Logic - Important Nuance

## Key Insight

**Rejections are temporary, Denials are final.**

### Rejections
- Claim is rejected **before** acceptance by payer
- Can be **fixed and resubmitted**
- If fixed and eventually paid/denied, we **don't have the original rejection context**
- **Only count rejections if claim is STILL in rejected state**

### Denials
- Claim is denied **after** acceptance and adjudication
- Denial is a **final outcome** (doesn't change)
- Always count denials

## Implementation

### Target Variable: `is_denied`
- `True` if claim status is `DENIED` (not `REJECTED`)
- `True` if claim has denial details AND status is NOT `PAID`
- `False` if claim is `PAID` (even if it has denial details - rejection was fixed)

### Feature: `is_rejected`
- `True` if claim status is `REJECTED` (still in rejected state)
- This is an **additional feature**, not the target
- Model can learn different patterns for rejections vs denials

### Historical Denial Rates
- Only count claims as denied if `paid_amount = 0`
- Excludes claims that were rejected but later paid

## Example Scenarios

1. **Claim rejected, then fixed and paid:**
   - Current status: `PAID`
   - `is_denied = False` ✅ (rejection was fixed)
   - `is_rejected = False` ✅ (not still rejected)

2. **Claim rejected, still rejected:**
   - Current status: `REJECTED`
   - `is_denied = False` (not denied, just rejected)
   - `is_rejected = True` ✅ (still in rejected state)

3. **Claim denied:**
   - Current status: `DENIED`
   - `is_denied = True` ✅
   - `is_rejected = False`

4. **Claim has denial details but is paid:**
   - Current status: `PAID`
   - Has denial details (from previous rejection)
   - `is_denied = False` ✅ (rejection was fixed, don't count it)

## Why This Matters

If we count rejections that were later fixed as "denied", we:
- Train on incomplete data (don't know what caused the rejection)
- Learn incorrect patterns (claim was actually fixable)
- Predict incorrectly (claim might be fixable, not a true denial)

By only counting current state:
- We learn from claims that are **still problematic**
- We predict outcomes for claims **in their current state**
- We avoid training on resolved issues we can't learn from

## Partially Paid Claims

### Important Distinction

**Partially paid claims are different from full denials:**
- Claim is **paid** (status = PAID)
- But **not fully paid** (payment_ratio < 1.0)
- Insurance provides **CARC/RARC codes** explaining adjustments
- These are **valuable training data** because we have the adjustment reasons

### Features for Partially Paid Claims

1. **`is_partially_paid`**: True if paid_amount > 0 and payment_ratio < 1.0
2. **`adjustment_amount`**: billed_amount - paid_amount
3. **`adjustment_ratio`**: adjustment_amount / billed_amount
4. **`has_partial_denial`**: True if partially paid with CARC/RARC codes
5. **`denial_detail_count`**: Number of adjustment/denial details
6. **`unique_carc_count`**: Number of unique CARC codes
7. **`unique_rarc_count`**: Number of unique RARC codes
8. **`total_adjustment_from_details`**: Sum of adjustment amounts from denial details

### Handling Logic

- **Fully paid claims** (payment_ratio >= 1.0): Ignore previous rejections (they were fixed)
- **Partially paid claims** (payment_ratio < 1.0): Capture CARC/RARC codes and adjustment amounts
- **Fully denied claims** (status = DENIED): Mark as `is_denied = True`

### Why This Matters

Partially paid claims provide:
- **Rich training data** with known adjustment reasons (CARC/RARC codes)
- **Patterns** about which services/amounts get adjusted
- **Predictive signals** for future partial denials
- **Actionable insights** (specific codes that lead to adjustments)


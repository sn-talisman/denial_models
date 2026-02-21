# Tebra Database Schema Documentation

*Source database*: `tebra_dw` — PostgreSQL data warehouse  
*Schema*: `tebra`  
*Last updated*: February 2026 (schema refresh with direct practice_guid foreign keys)

---

## Table of Contents

1. [Overview](#overview)
2. [Entity Relationship Diagram](#entity-relationship-diagram)
3. [Join Map — How the Application Queries](#join-map--how-the-application-queries)
4. [Table Definitions](#table-definitions)
5. [Key Design Notes](#key-design-notes)

---

## Overview

| Metric | Value |
|---|---|
| Total Tables | 10 |
| Total Views | 0 |
| Total Foreign Key Relationships | 6 |
| Claims Table | `fin_claim_line` (one row per claim line item) |
| Claim Grouping | `claim_reference_id` groups line items into a single claim |
| Practice Linkage | Direct `practice_guid` UUID on `fin_claim_line` |
| Payer Linkage | Via `clin_encounter.insurance_policy_key` → `ref_insurance_policy.policy_key` |

---

## Entity Relationship Diagram

```
                         ┌──────────────────────┐
                         │    cmn_practice       │
                         │ ──────────────────    │
                         │  practice_guid (PK)   │
                         │  name                 │
                         │  active               │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────────┐
                    │ practice_guid │                    │ practice_guid
                    ▼               ▼                    ▼
         ┌──────────────────┐  ┌───────────────────┐  ┌────────────────────┐
         │  fin_claim_line   │  │ clin_encounter     │  │  cmn_location      │
         │ ────────────────  │  │ ─────────────────  │  │ ────────────────── │
         │  tebra_claim_id   │  │  encounter_id (PK) │  │  location_guid(PK) │
         │  claim_reference  │  │  encounter_guid    │  │  name              │
         │  encounter_id ────┼─▶│  start_date        │  │  address_block     │
         │  practice_guid ───┤  │  patient_guid ─────┼──┼──────────────────┐ │
         │  patient_guid     │  │  provider_guid ────┼──┼─────────┐       │ │
         │  proc_code        │  │  location_guid ────┼─▶│         │       │ │
         │  billed_amount    │  │  insurance_policy  │  └─────────┼───────┘ │
         │  paid_amount      │  │    _key ───────────┤            │         │
         │  claim_status     │  │  referring_provider│  ┌─────────▼───────┐ │
         │  payer_status     │  │    _guid           │  │  cmn_provider    │ │
         │  adjustments_json │  └──────────┬─────────┘  │ ──────────────  │ │
         │  adjustment_desc  │             │            │  provider_guid  │ │
         └──────────┬────────┘             │            │  npi            │ │
                    │                      │            │  name           │ │
                    │ claim_reference_id   │            └─────────────────┘ │
                    ▼                      │                                │
         ┌──────────────────┐              │ encounter_id   ┌──────────────▼──┐
         │  fin_era_bundle   │              ▼               │  cmn_patient     │
         │ ────────────────  │  ┌──────────────────────┐   │ ──────────────── │
         │  claim_ref (PK)   │  │ clin_encounter_diag  │   │  patient_guid    │
         │  payer_name       │  │ ──────────────────── │   │  patient_id      │
         │  received_date    │  │  encounter_id (FK)   │   │  full_name (PHI) │
         │  total_paid       │  │  diag_code (ICD-10)  │   │  dob (PHI)       │
         │  total_patient    │  │  precedence          │   │  gender          │
         │    _resp          │  │  description         │   └──────────────────┘
         │  era_report_id ───┤  └──────────────────────┘
         └──────────────────┘                               ┌──────────────────┐
                    │                                       │ ref_insurance    │
                    │ era_report_id        insurance_policy │   _policy         │
                    ▼                        _key           │ ──────────────── │
         ┌──────────────────┐       ◀──────────────────────│  policy_key (PK) │
         │  fin_era_report   │                              │  company_name    │
         │ ────────────────  │                              │  plan_name       │
         │  era_report_id    │                              │  policy_number   │
         │  file_name        │                              │  copay           │
         │  payer_name       │                              └──────────────────┘
         │  total_paid       │
         │  practice_guid    │
         │  denied_count     │
         │  rejected_count   │
         └──────────────────┘
```

---

## Join Map — How the Application Queries

The application's `DatabaseClaimsRepository` (`src/data_access/db_repository.py`) uses these joins:

### Claims Query (`get_claims`)

```sql
FROM tebra.fin_claim_line cl
LEFT JOIN tebra.clin_encounter e        ON cl.encounter_id = e.encounter_id
LEFT JOIN tebra.ref_insurance_policy ip ON e.insurance_policy_key = ip.policy_key
```

**Key field mappings**:

| Application Field | SQL Expression | Source Table |
|---|---|---|
| `practice_id` | `cl.practice_guid::text` | `fin_claim_line` (direct FK to `cmn_practice`) |
| `payer_id` | `ip.policy_key` | `ref_insurance_policy` (via encounter) |
| `patient_id` | `COALESCE(cl.patient_guid, e.patient_guid)::text` | `fin_claim_line` or `clin_encounter` |
| `provider_id` | `e.provider_guid::text` | `clin_encounter` |
| `is_secondary_claim` | `ip.precedence > 1` | `ref_insurance_policy` |
| `has_referral` | `e.referring_provider_guid IS NOT NULL` | `clin_encounter` |

Claims are grouped by `claim_reference_id` (using `DISTINCT ON`). Billed/paid amounts are aggregated across all line items sharing the same `claim_reference_id`.

### Practices Query (`get_practices`)

```sql
FROM tebra.cmn_practice cp
INNER JOIN tebra.fin_claim_line cl ON cl.practice_guid = cp.practice_guid
WHERE cp.active = TRUE AND cp.name IS NOT NULL
```

Only returns practices that have at least one claim line item. No fuzzy name matching.

### Line Items Query (`get_claim_line_items`)

```sql
FROM tebra.fin_claim_line cl
LEFT JOIN tebra.clin_encounter e ON cl.encounter_id = e.encounter_id
```

Also fetches:
- **ICD-10 codes** via subquery on `clin_encounter_diagnosis` (joined by `encounter_id`)
- **Place of service** from `clin_encounter.place_of_service_code`
- **Modifiers** parsed from `cl.modifiers_json` (JSONB)

### Denial Details Query (`get_denial_details`)

```sql
FROM tebra.fin_claim_line
WHERE claim_reference_id = :claim_id OR tebra_claim_id = :claim_id
```

CARC/RARC codes are extracted from:
1. `adjustments_json` — parsed as JSON array of `{"carc_code": N, "rarc_code": "X", "amount": N}`
2. `adjustment_descriptions` — parsed via regex for patterns like `CO-45`, `PR-1`

### Historical Denial Rates (`get_historical_denial_rates`)

```sql
FROM tebra.fin_claim_line cl
LEFT JOIN tebra.clin_encounter e        ON cl.encounter_id = e.encounter_id
LEFT JOIN tebra.ref_insurance_policy ip ON e.insurance_policy_key = ip.policy_key
GROUP BY <dynamic grouping columns>
HAVING COUNT(*) >= 5
```

Supported groupings: `payer_id`, `practice_id`, `cpt_code`, `provider_id`, `carc_code`.

---

## Table Definitions

### tebra.cmn_practice

Medical practices / organizations.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `practice_guid` | UUID | No (PK) | Unique practice identifier |
| `name` | TEXT | Yes | Practice display name |
| `active` | BOOLEAN | Yes (default: true) | Whether practice is active |

**Indexes**: `cmn_practice_pkey` (unique, btree on `practice_guid`)

---

### tebra.cmn_provider

Healthcare providers.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `provider_guid` | UUID | No (PK) | Unique provider identifier |
| `npi` | VARCHAR(20) | Yes | National Provider Identifier |
| `name` | VARCHAR(150) | Yes | Provider name |

**Indexes**: `cmn_provider_pkey` (unique, btree on `provider_guid`)

---

### tebra.cmn_patient

Patient demographics. **Contains PHI — handle with care.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `patient_guid` | UUID | No (PK) | Unique patient identifier |
| `patient_id` | VARCHAR(50) | Yes | External patient ID |
| `full_name` | VARCHAR(150) | Yes | Full name (**PHI**) |
| `case_id` | VARCHAR(50) | Yes | Case identifier |
| `dob` | DATE | Yes | Date of birth (**PHI**) |
| `gender` | TEXT | Yes | Gender |
| `address_line1` | TEXT | Yes | Street address (**PHI**) |
| `city` | TEXT | Yes | City |
| `state` | TEXT | Yes | State |
| `zip` | TEXT | Yes | ZIP code |

**Indexes**: `cmn_patient_pkey`, `idx_pat_name`

---

### tebra.cmn_location

Practice locations / facilities.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `location_guid` | UUID | No (PK) | Unique location identifier |
| `name` | VARCHAR(150) | Yes | Location name |
| `address_block` | JSONB | Yes | Structured address data |

**Indexes**: `cmn_location_pkey`

---

### tebra.ref_insurance_policy

Insurance payer and plan information.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `policy_key` | VARCHAR(100) | No (PK) | Unique policy/payer identifier |
| `company_name` | VARCHAR(150) | Yes | Insurance company name |
| `plan_name` | VARCHAR(150) | Yes | Plan name (HMO, PPO, etc.) |
| `policy_number` | VARCHAR(50) | Yes | Policy number |
| `group_number` | VARCHAR(50) | Yes | Group number |
| `start_date` | DATE | Yes | Policy start date |
| `end_date` | DATE | Yes | Policy end date |
| `copay` | NUMERIC | Yes | Copay amount |
| `precedence` | INTEGER | Yes | 1 = primary, 2+ = secondary |

**Indexes**: `ref_insurance_policy_pkey`

---

### tebra.clin_encounter

Clinical encounters / appointments.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `encounter_id` | BIGINT | No (PK) | Unique encounter identifier |
| `encounter_guid` | UUID | Yes | GUID form of encounter ID |
| `start_date` | DATE | Yes | Encounter date |
| `status` | VARCHAR(50) | Yes | Encounter status |
| `appt_type` | VARCHAR(100) | Yes | Appointment type |
| `appt_reason` | TEXT | Yes | Reason for visit |
| `patient_guid` | UUID | Yes (FK) | → `cmn_patient.patient_guid` |
| `provider_guid` | UUID | Yes (FK) | → `cmn_provider.provider_guid` |
| `location_guid` | UUID | Yes (FK) | → `cmn_location.location_guid` |
| `insurance_policy_key` | VARCHAR(100) | Yes (FK) | → `ref_insurance_policy.policy_key` |
| `practice_guid` | UUID | Yes | → `cmn_practice.practice_guid` (direct FK) |
| `place_of_service_code` | TEXT | Yes | Place of service code |
| `referring_provider_guid` | TEXT | Yes | Referring provider GUID |

**Indexes**: `clin_encounter_pkey`, `idx_enc_patient`, `idx_enc_provider`, `idx_enc_location`, `idx_enc_insurance`, `idx_enc_date`

**Foreign Keys**:
- `patient_guid` → `cmn_patient.patient_guid`
- `provider_guid` → `cmn_provider.provider_guid`
- `location_guid` → `cmn_location.location_guid`
- `insurance_policy_key` → `ref_insurance_policy.policy_key`

---

### tebra.clin_encounter_diagnosis

ICD-10 diagnosis codes per encounter.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `encounter_id` | BIGINT | No (PK, FK) | → `clin_encounter.encounter_id` |
| `diag_code` | VARCHAR(20) | No (PK) | ICD-10 diagnosis code |
| `precedence` | INTEGER | Yes | Diagnosis order (1 = primary) |
| `description` | TEXT | Yes | Diagnosis description |

**Indexes**: `clin_encounter_diagnosis_pkey` (composite on `encounter_id`, `diag_code`)

---

### tebra.fin_claim_line

Claim line items — the **central billing table**. Each row represents one procedure billed on a claim.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `tebra_claim_id` | TEXT | No (PK) | Unique line item identifier |
| `encounter_id` | BIGINT | Yes (FK) | → `clin_encounter.encounter_id` |
| `claim_reference_id` | VARCHAR(100) | Yes | Groups line items into a single claim |
| `proc_code` | VARCHAR(20) | Yes | CPT/HCPCS code (may be formatted as `HC:92507:GN`) |
| `description` | TEXT | Yes | Procedure description |
| `date_of_service` | DATE | Yes | Service date |
| `billed_amount` | NUMERIC | Yes | Amount billed |
| `paid_amount` | NUMERIC | Yes | Amount paid by payer |
| `units` | INTEGER | Yes | Number of units |
| `adjustments_json` | TEXT | Yes | JSON array of adjustment objects |
| `adjustment_descriptions` | TEXT | Yes | Text descriptions like `CO-45: Fee schedule` |
| `modifiers_json` | JSONB | Yes | Procedure modifiers |
| `claim_status` | TEXT | Yes | Internal workflow status |
| `payer_status` | TEXT | Yes | Payer response status |
| `clearinghouse_payer` | TEXT | Yes | Clearinghouse payer name |
| `tracking_number` | TEXT | Yes | Clearinghouse tracking number |
| `practice_guid` | UUID | Yes | → `cmn_practice.practice_guid` (direct FK) |
| `patient_guid` | UUID | Yes | → `cmn_patient.patient_guid` |

**Indexes**: `fin_claim_line_pkey`, `idx_claim_encounter`, `idx_claim_era`

**Important**: `claim_reference_id` is used to group multiple line items into a single logical claim. The application uses `DISTINCT ON (cl.claim_reference_id)` to deduplicate.

---

### tebra.fin_era_bundle

Electronic Remittance Advice (ERA) bundles — one per claim adjudication.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `claim_reference_id` | VARCHAR(100) | No (PK) | → matches `fin_claim_line.claim_reference_id` |
| `payer_name` | VARCHAR(150) | Yes | Payer name from ERA |
| `received_date` | TIMESTAMP | Yes | Date ERA was received (used as adjudication date) |
| `total_paid` | NUMERIC | Yes | Total paid amount |
| `total_patient_resp` | NUMERIC | Yes | Total patient responsibility |
| `era_report_id` | TEXT | Yes (FK) | → `fin_era_report.era_report_id` |

**Indexes**: `fin_era_bundle_pkey`, `idx_era_payer`, `idx_era_bundle_report_id`

---

### tebra.fin_era_report

ERA report metadata — one report can contain multiple ERA bundles.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `era_report_id` | TEXT | No (PK) | Unique report identifier |
| `file_name` | TEXT | Yes | Source file name |
| `received_date` | TIMESTAMP | Yes | Date received |
| `payer_name` | TEXT | Yes | Payer name |
| `payer_id` | TEXT | Yes | Payer identifier |
| `check_number` | TEXT | Yes | Payment check number |
| `check_date` | DATE | Yes | Payment date |
| `total_paid` | NUMERIC | Yes | Total payment amount |
| `payment_method` | TEXT | Yes | Payment method (EFT, check, etc.) |
| `practice_guid` | TEXT | Yes | Practice GUID |
| `denied_count` | INTEGER | Yes (default: 0) | Number of denied claims |
| `rejected_count` | INTEGER | Yes (default: 0) | Number of rejected claims |
| `claim_count_source` | INTEGER | Yes (default: 0) | Source claim count |
| `created_at` | TIMESTAMP | Yes (default: now()) | Record creation timestamp |

**Indexes**: `fin_era_report_pkey`

---

## Key Design Notes

### Practice GUID — Direct Foreign Keys (Feb 2026 Schema Update)

The database schema was updated in February 2026 to add direct `practice_guid` foreign keys on:
- `fin_claim_line.practice_guid`
- `clin_encounter.practice_guid`
- `cmn_location.practice_guid`

**Before**: Practice linkage required fragile fuzzy name matching between `cmn_location.name` and `cmn_practice.name`, which missed practices with truncated or mismatched names.

**After**: All joins use explicit UUID foreign keys. The application joins `fin_claim_line.practice_guid = cmn_practice.practice_guid` directly.

### Claim Grouping

A single "claim" in the application corresponds to all `fin_claim_line` rows sharing the same `claim_reference_id`. The application uses `DISTINCT ON (cl.claim_reference_id)` to collapse line items into one `Claim` object, with aggregated billed/paid amounts computed via subqueries.

### Status Determination

The database stores two status fields:
- `claim_status` — internal workflow status (e.g., "Completed", "Submitted")
- `payer_status` — payer's response (e.g., "Paid", "Denied", "Rejected")

The application's `_map_claim_status()` method resolves these into a single `ClaimStatus` enum with `payer_status` taking priority for denial/rejection determination.

### CARC/RARC Code Extraction

Denial reason codes are stored in two forms in `fin_claim_line`:
1. `adjustments_json` — A TEXT field containing a JSON array of adjustment objects with `carc_code`, `rarc_code`, and `amount` fields.
2. `adjustment_descriptions` — A TEXT field with human-readable descriptions like `"CO-45: Charge exceeds fee schedule | PR-1: Deductible"`.

The application parses both, preferring structured JSON when available and falling back to regex extraction from descriptions.

### PHI Handling

Patient data in `cmn_patient` (name, DOB, address) is PHI. The application:
- Uses only `patient_guid` as an identifier (never exposes name/DOB via API)
- Redacts PHI in structured logs when `REDACT_PHI_IN_LOGS=true`
- Never sends patient data to external services

# Tebra Database Schema Documentation

*Generated automatically from database introspection*


## Overview


- **Total Tables**: 10

- **Total Views**: 0

- **Total Relationships**: 5


## Tables


### tebra.clin_encounter


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `encounter_id` | bigint | No | - | |

| `encounter_guid` | uuid | Yes | - | |

| `start_date` | date | Yes | - | |

| `status` | character varying(50) | Yes | - | |

| `appt_type` | character varying(100) | Yes | - | |

| `appt_reason` | text | Yes | - | |

| `patient_guid` | uuid | Yes | - | |

| `provider_guid` | uuid | Yes | - | |

| `location_guid` | uuid | Yes | - | |

| `insurance_policy_key` | character varying(100) | Yes | - | |

| `appt_subject` | text | Yes | - | |

| `appt_notes` | text | Yes | - | |

| `pos_description` | text | Yes | - | |

| `referring_provider_guid` | text | Yes | - | |


**Primary Keys**: `encounter_id`


**Foreign Keys**:


- `patient_guid` → `tebra.cmn_patient.patient_guid`

- `provider_guid` → `tebra.cmn_provider.provider_guid`

- `location_guid` → `tebra.cmn_location.location_guid`

- `insurance_policy_key` → `tebra.ref_insurance_policy.policy_key`



**Indexes**:


- `clin_encounter_pkey`: CREATE UNIQUE INDEX clin_encounter_pkey ON tebra.clin_encounter USING btree (encounter_id)

- `idx_enc_patient`: CREATE INDEX idx_enc_patient ON tebra.clin_encounter USING btree (patient_guid)

- `idx_enc_provider`: CREATE INDEX idx_enc_provider ON tebra.clin_encounter USING btree (provider_guid)

- `idx_enc_location`: CREATE INDEX idx_enc_location ON tebra.clin_encounter USING btree (location_guid)

- `idx_enc_insurance`: CREATE INDEX idx_enc_insurance ON tebra.clin_encounter USING btree (insurance_policy_key)

- `idx_enc_date`: CREATE INDEX idx_enc_date ON tebra.clin_encounter USING btree (start_date)



---


### tebra.clin_encounter_diagnosis


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `encounter_id` | bigint | No | - | |

| `diag_code` | character varying(20) | No | - | |

| `precedence` | integer | Yes | - | |

| `description` | text | Yes | - | |


**Primary Keys**: `encounter_id`, `diag_code`


**Foreign Keys**:


- `encounter_id` → `tebra.clin_encounter.encounter_id`



**Indexes**:


- `clin_encounter_diagnosis_pkey`: CREATE UNIQUE INDEX clin_encounter_diagnosis_pkey ON tebra.clin_encounter_diagnosis USING btree (encounter_id, diag_code)



---


### tebra.cmn_location


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `location_guid` | uuid | No | - | |

| `name` | character varying(150) | Yes | - | |

| `address_block` | jsonb | Yes | - | |


**Primary Keys**: `location_guid`


**Indexes**:


- `cmn_location_pkey`: CREATE UNIQUE INDEX cmn_location_pkey ON tebra.cmn_location USING btree (location_guid)



---


### tebra.cmn_patient


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `patient_guid` | uuid | No | - | |

| `patient_id` | character varying(50) | Yes | - | |

| `full_name` | character varying(150) | Yes | - | |

| `case_id` | character varying(50) | Yes | - | |

| `dob` | date | Yes | - | |

| `gender` | text | Yes | - | |

| `address_line1` | text | Yes | - | |

| `city` | text | Yes | - | |

| `state` | text | Yes | - | |

| `zip` | text | Yes | - | |


**Primary Keys**: `patient_guid`


**Indexes**:


- `cmn_patient_pkey`: CREATE UNIQUE INDEX cmn_patient_pkey ON tebra.cmn_patient USING btree (patient_guid)

- `idx_pat_name`: CREATE INDEX idx_pat_name ON tebra.cmn_patient USING btree (full_name)



---


### tebra.cmn_practice


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `practice_guid` | uuid | No | - | |

| `name` | text | Yes | - | |

| `active` | boolean | Yes | true | |


**Primary Keys**: `practice_guid`


**Indexes**:


- `cmn_practice_pkey`: CREATE UNIQUE INDEX cmn_practice_pkey ON tebra.cmn_practice USING btree (practice_guid)



---


### tebra.cmn_provider


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `provider_guid` | uuid | No | - | |

| `npi` | character varying(20) | Yes | - | |

| `name` | character varying(150) | Yes | - | |


**Primary Keys**: `provider_guid`


**Indexes**:


- `cmn_provider_pkey`: CREATE UNIQUE INDEX cmn_provider_pkey ON tebra.cmn_provider USING btree (provider_guid)



---


### tebra.fin_claim_line


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `tebra_claim_id` | text | No | - | |

| `encounter_id` | bigint | Yes | - | |

| `claim_reference_id` | character varying(100) | Yes | - | |

| `proc_code` | character varying(20) | Yes | - | |

| `description` | text | Yes | - | |

| `date_of_service` | date | Yes | - | |

| `billed_amount` | numeric | Yes | - | |

| `paid_amount` | numeric | Yes | - | |

| `units` | integer | Yes | - | |

| `adjustments_json` | text | Yes | - | |

| `adjustment_descriptions` | text | Yes | - | |

| `modifiers_json` | jsonb | Yes | - | |

| `claim_status` | text | Yes | - | |

| `payer_status` | text | Yes | - | |

| `clearinghouse_payer` | text | Yes | - | |

| `tracking_number` | text | Yes | - | |

| `practice_guid` | uuid | Yes | - | |


**Primary Keys**: `tebra_claim_id`


**Indexes**:


- `idx_claim_encounter`: CREATE INDEX idx_claim_encounter ON tebra.fin_claim_line USING btree (encounter_id)

- `idx_claim_era`: CREATE INDEX idx_claim_era ON tebra.fin_claim_line USING btree (claim_reference_id)

- `fin_claim_line_pkey`: CREATE UNIQUE INDEX fin_claim_line_pkey ON tebra.fin_claim_line USING btree (tebra_claim_id)



---


### tebra.fin_era_bundle


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `claim_reference_id` | character varying(100) | No | - | |

| `payer_name` | character varying(150) | Yes | - | |

| `received_date` | timestamp without time zone | Yes | - | |

| `total_paid` | numeric | Yes | - | |

| `total_patient_resp` | numeric | Yes | - | |

| `era_report_id` | text | Yes | - | |


**Primary Keys**: `claim_reference_id`


**Indexes**:


- `fin_era_bundle_pkey`: CREATE UNIQUE INDEX fin_era_bundle_pkey ON tebra.fin_era_bundle USING btree (claim_reference_id)

- `idx_era_payer`: CREATE INDEX idx_era_payer ON tebra.fin_era_bundle USING btree (payer_name)

- `idx_era_bundle_report_id`: CREATE INDEX idx_era_bundle_report_id ON tebra.fin_era_bundle USING btree (era_report_id)



---


### tebra.fin_era_report


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `era_report_id` | text | No | - | |

| `file_name` | text | Yes | - | |

| `received_date` | timestamp without time zone | Yes | - | |

| `payer_name` | text | Yes | - | |

| `payer_id` | text | Yes | - | |

| `check_number` | text | Yes | - | |

| `check_date` | date | Yes | - | |

| `total_paid` | numeric | Yes | - | |

| `payment_method` | text | Yes | - | |

| `created_at` | timestamp without time zone | Yes | now() | |

| `practice_guid` | text | Yes | - | |

| `denied_count` | integer | Yes | 0 | |

| `rejected_count` | integer | Yes | 0 | |

| `claim_count_source` | integer | Yes | 0 | |

| `customer_id` | text | Yes | - | |

| `clearinghouse_response_id` | text | Yes | - | |

| `report_type_id` | integer | Yes | - | |

| `report_type_name` | text | Yes | - | |

| `source_type_id` | integer | Yes | - | |

| `source_type_name` | text | Yes | - | |

| `payment_id` | text | Yes | - | |

| `processed_flag` | boolean | Yes | - | |

| `response_type` | text | Yes | - | |

| `response_type_name` | text | Yes | - | |

| `reviewed_flag` | boolean | Yes | - | |

| `source_address` | text | Yes | - | |

| `title` | text | Yes | - | |

| `total_amount` | numeric | Yes | - | |


**Primary Keys**: `era_report_id`


**Indexes**:


- `fin_era_report_pkey`: CREATE UNIQUE INDEX fin_era_report_pkey ON tebra.fin_era_report USING btree (era_report_id)



---


### tebra.ref_insurance_policy


### Columns


| Column Name | Data Type | Nullable | Default | Description |

|------------|-----------|----------|---------|-------------|

| `policy_key` | character varying(100) | No | - | |

| `company_name` | character varying(150) | Yes | - | |

| `plan_name` | character varying(150) | Yes | - | |

| `policy_number` | character varying(50) | Yes | - | |

| `group_number` | character varying(50) | Yes | - | |

| `start_date` | date | Yes | - | |

| `end_date` | date | Yes | - | |

| `copay` | numeric | Yes | - | |


**Primary Keys**: `policy_key`


**Indexes**:


- `ref_insurance_policy_pkey`: CREATE UNIQUE INDEX ref_insurance_policy_pkey ON tebra.ref_insurance_policy USING btree (policy_key)



---


## Entity Relationship Summary


### Key Entities (Inferred)


- **Claims**: fin_claim_line

- **Payers**: ref_insurance_policy

- **Practices**: cmn_practice

- **Patients**: cmn_patient

- **Providers**: cmn_provider

- **Diagnoses**: clin_encounter_diagnosis

- **Remittance**: fin_era_bundle, fin_era_report


### Relationships


- `tebra.clin_encounter.patient_guid` → `tebra.cmn_patient.patient_guid`

- `tebra.clin_encounter.provider_guid` → `tebra.cmn_provider.provider_guid`

- `tebra.clin_encounter.location_guid` → `tebra.cmn_location.location_guid`

- `tebra.clin_encounter.insurance_policy_key` → `tebra.ref_insurance_policy.policy_key`

- `tebra.clin_encounter_diagnosis.encounter_id` → `tebra.clin_encounter.encounter_id`

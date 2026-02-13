"""PostgreSQL database repository implementation.

This implementation provides direct database access using SQLAlchemy async.
It queries the actual tebra database tables and maps results to Pydantic models.

Schema (updated 2026-02-13):
  - fin_claim_line.practice_guid → cmn_practice.practice_guid  (direct FK)
  - clin_encounter.practice_guid → cmn_practice.practice_guid  (direct FK)
  - cmn_location.practice_guid  → cmn_practice.practice_guid  (direct FK)
  - fin_claim_line.encounter_id → clin_encounter.encounter_id
  - clin_encounter.location_guid → cmn_location.location_guid
  - clin_encounter.insurance_policy_key → ref_insurance_policy.policy_key
  - fin_claim_line.patient_guid → cmn_patient.patient_guid
  - clin_encounter.provider_guid → cmn_provider.provider_guid
  - clin_encounter_diagnosis.encounter_id → clin_encounter.encounter_id
"""

import os
import json
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.data_access.models import (
    Claim,
    ClaimLineItem,
    DenialDetail,
    Practice,
    Payer,
    DenialRateRecord,
    ClaimStatus,
)

logger = structlog.get_logger(__name__)


class DatabaseClaimsRepository(ClaimsRepository):
    """PostgreSQL database repository implementation.
    
    All practice joins use explicit practice_guid foreign keys.
    No fuzzy name matching is needed.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database repository.
        
        Args:
            database_url: PostgreSQL connection URL. If None, reads from DATABASE_URL env var.
        """
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/tebra"
            )
        
        # Ensure asyncpg driver is used
        if not database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Database repository initialized", database_url=database_url.split("@")[0] + "@***")
    
    def _map_claim_status(self, claim_status: Optional[str], payer_status: Optional[str]) -> ClaimStatus:
        """Map database status fields to ClaimStatus enum.
        
        IMPORTANT: payer_status takes precedence for rejections and denials
        because it reflects the payer's actual response, while claim_status
        may just indicate internal workflow state.
        """
        if not claim_status and not payer_status:
            return ClaimStatus.PENDING
        
        payer_status_lower = (payer_status or "").lower()
        claim_status_lower = (claim_status or "").lower()
        
        # Priority 1: Check for rejections first (in either field)
        if "rejected" in payer_status_lower or "reject" in payer_status_lower:
            return ClaimStatus.REJECTED
        if "rejected" in claim_status_lower or "reject" in claim_status_lower:
            return ClaimStatus.REJECTED
        
        # Priority 2: Check for denials
        if "denied" in payer_status_lower or "denial" in payer_status_lower:
            return ClaimStatus.DENIED
        if "denied" in claim_status_lower or "denial" in claim_status_lower:
            return ClaimStatus.DENIED
        
        # Priority 3: Check for paid (but only if not rejected/denied above)
        if "paid" in payer_status_lower:
            return ClaimStatus.PAID
        if "paid" in claim_status_lower:
            return ClaimStatus.PAID
        
        # Priority 4: Check for completed (only if payer_status is also paid)
        if "complete" in claim_status_lower and "paid" in payer_status_lower:
            return ClaimStatus.PAID
        
        # Priority 5: Check for submitted/pending
        if "submitted" in claim_status_lower or "submitted" in payer_status_lower:
            return ClaimStatus.SUBMITTED
        if "pending" in claim_status_lower or "pending" in payer_status_lower:
            return ClaimStatus.PENDING
        
        # Priority 6: Other statuses
        if "appealed" in claim_status_lower or "appealed" in payer_status_lower:
            return ClaimStatus.APPEALED
        if "void" in claim_status_lower or "void" in payer_status_lower:
            return ClaimStatus.VOIDED
        
        # Default
        return ClaimStatus.PENDING
    
    async def get_claims(
        self,
        practice_id: Optional[str] = None,
        payer_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Claim]:
        """Retrieve claims with optional filters.
        
        Uses direct GUID joins:
          fin_claim_line.practice_guid → cmn_practice.practice_guid
          fin_claim_line.encounter_id → clin_encounter.encounter_id
          clin_encounter.insurance_policy_key → ref_insurance_policy.policy_key
        """
        async with self.session_factory() as session:
            query = text("""
                SELECT DISTINCT ON (cl.claim_reference_id)
                    cl.claim_reference_id as claim_id,
                    cl.practice_guid::text as practice_id,
                    ip.policy_key as payer_id,
                    COALESCE(cl.patient_guid, e.patient_guid)::text as patient_id,
                    e.provider_guid::text as provider_id,
                    cl.claim_reference_id as claim_number,
                    cl.claim_status,
                    cl.payer_status,
                    (SELECT MIN(date_of_service) FROM tebra.fin_claim_line 
                     WHERE claim_reference_id = cl.claim_reference_id) as service_date_from,
                    (SELECT MAX(date_of_service) FROM tebra.fin_claim_line 
                     WHERE claim_reference_id = cl.claim_reference_id) as service_date_to,
                    NULL as submitted_date,
                    (SELECT received_date FROM tebra.fin_era_bundle 
                     WHERE claim_reference_id = cl.claim_reference_id LIMIT 1) as adjudicated_date,
                    (SELECT SUM(billed_amount) FROM tebra.fin_claim_line 
                     WHERE claim_reference_id = cl.claim_reference_id) as total_billed_amount,
                    (SELECT SUM(paid_amount) FROM tebra.fin_claim_line 
                     WHERE claim_reference_id = cl.claim_reference_id) as total_paid_amount,
                    (SELECT SUM(paid_amount) FROM tebra.fin_claim_line 
                     WHERE claim_reference_id = cl.claim_reference_id) as total_allowed_amount,
                    CASE WHEN ip.precedence > 1 THEN TRUE ELSE FALSE END as is_secondary_claim,
                    FALSE as has_prior_auth,
                    CASE WHEN e.referring_provider_guid IS NOT NULL THEN TRUE ELSE FALSE END as has_referral
                FROM tebra.fin_claim_line cl
                LEFT JOIN tebra.clin_encounter e ON cl.encounter_id = e.encounter_id
                LEFT JOIN tebra.ref_insurance_policy ip ON e.insurance_policy_key = ip.policy_key
                WHERE 1=1
            """)
            
            params = {}
            
            if practice_id:
                query = text(str(query) + " AND cl.practice_guid::text = :practice_id")
                params["practice_id"] = practice_id
            
            if payer_id:
                query = text(str(query) + " AND ip.policy_key = :payer_id")
                params["payer_id"] = payer_id
            
            if date_from:
                query = text(str(query) + " AND cl.date_of_service >= :date_from")
                params["date_from"] = date_from
            
            if date_to:
                query = text(str(query) + " AND cl.date_of_service <= :date_to")
                params["date_to"] = date_to
            
            if status:
                status_lower = status.lower()
                if "denied" in status_lower:
                    query = text(str(query) + " AND (cl.claim_status ILIKE '%denied%' OR cl.payer_status ILIKE '%denied%')")
                elif "rejected" in status_lower:
                    query = text(str(query) + " AND (cl.claim_status ILIKE '%rejected%' OR cl.payer_status ILIKE '%rejected%')")
                elif "paid" in status_lower:
                    query = text(str(query) + " AND cl.paid_amount > 0")
            
            if limit is not None:
                query = text(str(query) + """
                    ORDER BY cl.claim_reference_id
                    LIMIT :limit OFFSET :offset
                """)
                params["limit"] = limit
                params["offset"] = offset
            else:
                query = text(str(query) + """
                    ORDER BY cl.claim_reference_id
                    OFFSET :offset
                """)
                params["offset"] = offset
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            claims = []
            for row in rows:
                claim_status = self._map_claim_status(row.claim_status, row.payer_status)
                
                claim = Claim(
                    claim_id=row.claim_id or f"claim-{row.claim_number}",
                    practice_id=str(row.practice_id) if row.practice_id else "",
                    payer_id=str(row.payer_id) if row.payer_id else "",
                    patient_id=str(row.patient_id) if row.patient_id else None,
                    provider_id=str(row.provider_id) if row.provider_id else None,
                    claim_number=row.claim_number,
                    status=claim_status,
                    service_date_from=row.service_date_from,
                    service_date_to=row.service_date_to,
                    submitted_date=row.submitted_date,
                    adjudicated_date=row.adjudicated_date.date() if row.adjudicated_date else None,
                    total_billed_amount=Decimal(str(row.total_billed_amount or 0)),
                    total_allowed_amount=Decimal(str(row.total_allowed_amount or 0)) if row.total_allowed_amount else None,
                    total_paid_amount=Decimal(str(row.total_paid_amount or 0)) if row.total_paid_amount else None,
                    is_secondary_claim=row.is_secondary_claim or False,
                    has_prior_auth=row.has_prior_auth or False,
                    has_referral=row.has_referral or False,
                )
                claims.append(claim)
            
            logger.info("Retrieved claims", count=len(claims), filters=params)
            return claims
    
    async def get_claim_by_id(self, claim_id: str) -> Optional[Claim]:
        """Retrieve a single claim by ID.
        
        Uses direct GUID joins (no fuzzy name matching).
        """
        async with self.session_factory() as session:
            query = text("""
                SELECT DISTINCT ON (cl.claim_reference_id)
                    cl.claim_reference_id as claim_id,
                    cl.practice_guid::text as practice_id,
                    ip.policy_key as payer_id,
                    COALESCE(cl.patient_guid, e.patient_guid)::text as patient_id,
                    e.provider_guid::text as provider_id,
                    cl.claim_reference_id as claim_number,
                    cl.claim_status,
                    cl.payer_status,
                    MIN(cl.date_of_service) OVER (PARTITION BY cl.claim_reference_id) as service_date_from,
                    MAX(cl.date_of_service) OVER (PARTITION BY cl.claim_reference_id) as service_date_to,
                    NULL as submitted_date,
                    er.received_date as adjudicated_date,
                    SUM(cl.billed_amount) OVER (PARTITION BY cl.claim_reference_id) as total_billed_amount,
                    SUM(cl.paid_amount) OVER (PARTITION BY cl.claim_reference_id) as total_paid_amount,
                    SUM(cl.paid_amount) OVER (PARTITION BY cl.claim_reference_id) as total_allowed_amount
                FROM tebra.fin_claim_line cl
                LEFT JOIN tebra.clin_encounter e ON cl.encounter_id = e.encounter_id
                LEFT JOIN tebra.ref_insurance_policy ip ON e.insurance_policy_key = ip.policy_key
                LEFT JOIN tebra.fin_era_bundle er ON cl.claim_reference_id = er.claim_reference_id
                WHERE cl.tebra_claim_id = :claim_id OR cl.claim_reference_id = :claim_id
                ORDER BY cl.claim_reference_id
                LIMIT 1
            """)
            
            result = await session.execute(query, {"claim_id": claim_id})
            row = result.fetchone()
            
            if row:
                claim_status = self._map_claim_status(row.claim_status, row.payer_status)
                return Claim(
                    claim_id=row.claim_id or claim_id,
                    practice_id=str(row.practice_id) if row.practice_id else "",
                    payer_id=str(row.payer_id) if row.payer_id else "",
                    patient_id=str(row.patient_id) if row.patient_id else None,
                    provider_id=str(row.provider_id) if row.provider_id else None,
                    claim_number=row.claim_number,
                    status=claim_status,
                    service_date_from=row.service_date_from,
                    service_date_to=row.service_date_to,
                    submitted_date=row.submitted_date,
                    adjudicated_date=row.adjudicated_date.date() if row.adjudicated_date else None,
                    total_billed_amount=Decimal(str(row.total_billed_amount or 0)),
                    total_allowed_amount=Decimal(str(row.total_allowed_amount or 0)) if row.total_allowed_amount else None,
                    total_paid_amount=Decimal(str(row.total_paid_amount or 0)) if row.total_paid_amount else None,
                )
        
        return None
    
    async def get_denial_details(self, claim_id: str) -> list[DenialDetail]:
        """Get denial/rejection reasons for a claim.
        
        Parses adjustments_json and adjustment_descriptions from fin_claim_line 
        to extract CARC/RARC codes.
        """
        import re
        
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    tebra_claim_id,
                    claim_reference_id,
                    adjustments_json,
                    adjustment_descriptions,
                    claim_status,
                    payer_status,
                    date_of_service,
                    billed_amount,
                    paid_amount,
                    (billed_amount - COALESCE(paid_amount, 0)) as adjustment_amount
                FROM tebra.fin_claim_line
                WHERE claim_reference_id = :claim_id OR tebra_claim_id = :claim_id
            """)
            
            result = await session.execute(query, {"claim_id": claim_id})
            rows = result.fetchall()
            
            denial_details = []
            
            for idx, row in enumerate(rows):
                # Parse adjustments_json if available
                adjustments = None
                if row.adjustments_json:
                    try:
                        if isinstance(row.adjustments_json, str):
                            adjustments = json.loads(row.adjustments_json)
                        else:
                            adjustments = row.adjustments_json
                    except (json.JSONDecodeError, TypeError):
                        logger.debug("adjustments_json is not JSON, parsing as text", claim_id=claim_id)
                        adjustments = None
                
                # Extract CARC code from adjustment_descriptions
                # Format: "PR-1: Description | CO-45: Description"
                carc_code = None
                rarc_code = None
                
                if row.adjustment_descriptions:
                    carc_match = re.search(r'\b([A-Z]{2,3})-(\d{1,3})\b', row.adjustment_descriptions)
                    if carc_match:
                        code_num = carc_match.group(2)
                        try:
                            carc_code = int(code_num)
                        except ValueError:
                            pass
                
                line_adjustment_amount = Decimal(str(row.adjustment_amount or 0)) if row.adjustment_amount else None
                
                if adjustments and isinstance(adjustments, list):
                    for adj in adjustments:
                        if isinstance(adj, dict):
                            adj_carc = adj.get("carc_code") or adj.get("CARC")
                            adj_rarc = adj.get("rarc_code") or adj.get("RARC")
                            adj_remark = adj.get("remark_code") or adj.get("remark")
                            adj_amount = adj.get("adjustment_amount") or adj.get("amount")
                            
                            final_adjustment_amount = None
                            if adj_amount:
                                try:
                                    final_adjustment_amount = Decimal(str(adj_amount))
                                except (ValueError, TypeError):
                                    pass
                            elif line_adjustment_amount and line_adjustment_amount > 0:
                                final_adjustment_amount = line_adjustment_amount
                            
                            if adj_carc or adj_rarc or row.adjustment_descriptions or final_adjustment_amount:
                                denial_details.append(DenialDetail(
                                    denial_id=f"{claim_id}-{idx}-{len(denial_details)}",
                                    claim_id=claim_id,
                                    line_item_id=row.tebra_claim_id,
                                    carc_code=int(adj_carc) if adj_carc and str(adj_carc).isdigit() else carc_code,
                                    rarc_code=str(adj_rarc) if adj_rarc else None,
                                    remark_code=str(adj_remark) if adj_remark else None,
                                    denial_reason_text=row.adjustment_descriptions or adj.get("description", ""),
                                    denial_date=row.date_of_service,
                                    adjustment_amount=final_adjustment_amount,
                                ))
                
                # If we have adjustment descriptions but no JSON
                if not denial_details and (row.adjustment_descriptions or (line_adjustment_amount and line_adjustment_amount > 0)):
                    denial_details.append(DenialDetail(
                        denial_id=f"{claim_id}-{idx}",
                        claim_id=claim_id,
                        line_item_id=row.tebra_claim_id,
                        carc_code=carc_code,
                        denial_reason_text=row.adjustment_descriptions,
                        denial_date=row.date_of_service,
                        adjustment_amount=line_adjustment_amount if line_adjustment_amount and line_adjustment_amount > 0 else None,
                    ))
                
                # If no adjustments but status indicates denial
                if not denial_details and (row.claim_status and "denied" in row.claim_status.lower() or 
                                          row.payer_status and "denied" in row.payer_status.lower()):
                    denial_details.append(DenialDetail(
                        denial_id=f"{claim_id}-{idx}",
                        claim_id=claim_id,
                        line_item_id=row.tebra_claim_id,
                        denial_reason_text=row.adjustment_descriptions or f"Status: {row.claim_status or row.payer_status}",
                        denial_date=row.date_of_service,
                    ))
            
            logger.info("Retrieved denial details", claim_id=claim_id, count=len(denial_details))
            return denial_details
    
    async def get_practices(self) -> list[Practice]:
        """Retrieve all practices with claims.
        
        Uses direct GUID join: fin_claim_line.practice_guid → cmn_practice.practice_guid
        """
        async with self.session_factory() as session:
            query = text("""
                SELECT DISTINCT
                    cp.practice_guid::text as practice_id,
                    cp.name as practice_name
                FROM tebra.cmn_practice cp
                INNER JOIN tebra.fin_claim_line cl ON cl.practice_guid = cp.practice_guid
                WHERE cp.active = TRUE
                AND cp.name IS NOT NULL
                ORDER BY cp.name
            """)
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            practices = [
                Practice(
                    practice_id=row.practice_id,
                    name=row.practice_name or "",
                )
                for row in rows
            ]
            
            logger.info("Retrieved practices", 
                       count=len(practices),
                       note="Direct join: fin_claim_line.practice_guid → cmn_practice.practice_guid")
            return practices
    
    async def get_payers(self) -> list[Payer]:
        """Retrieve all payers."""
        async with self.session_factory() as session:
            query = text("""
                SELECT DISTINCT
                    policy_key as payer_id,
                    company_name as name,
                    plan_name,
                    NULL as payer_type
                FROM tebra.ref_insurance_policy
                WHERE company_name IS NOT NULL
                ORDER BY company_name
            """)
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            payers = [
                Payer(
                    payer_id=row.payer_id,
                    name=row.name or "",
                    payer_type=row.payer_type,
                    plan_type=row.plan_name,
                )
                for row in rows
            ]
            
            logger.info("Retrieved payers", count=len(payers))
            return payers
    
    async def get_historical_denial_rates(
        self,
        group_by: list[str],
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[DenialRateRecord]:
        """Aggregated denial rates for feature engineering.
        
        Uses direct GUID joins for all groupings.
        """
        async with self.session_factory() as session:
            group_by_clause = []
            select_fields = []
            
            valid_group_by = {
                "payer_id": "ip.policy_key",
                "practice_id": "cl.practice_guid::text",
                "cpt_code": "cl.proc_code",
                "provider_id": "e.provider_guid::text",
                "carc_code": "carc_code",
            }
            
            for field in group_by:
                if field in valid_group_by:
                    db_field = valid_group_by[field]
                    group_by_clause.append(db_field)
                    select_fields.append(f"{db_field} as {field}")
            
            if not select_fields:
                logger.warning("No valid group_by fields", group_by=group_by)
                return []
            
            # Only add joins that are needed
            joins = """
                LEFT JOIN tebra.clin_encounter e ON cl.encounter_id = e.encounter_id
                LEFT JOIN tebra.ref_insurance_policy ip ON e.insurance_policy_key = ip.policy_key
            """
            
            query = text(f"""
                SELECT 
                    {', '.join(select_fields)},
                    COUNT(*) as total_claims,
                    SUM(CASE 
                        WHEN (cl.claim_status ILIKE '%denied%' OR cl.payer_status ILIKE '%denied%')
                        AND (cl.claim_status NOT ILIKE '%rejected%' AND cl.payer_status NOT ILIKE '%rejected%')
                        AND (cl.paid_amount = 0 OR cl.paid_amount IS NULL)
                        THEN 1 ELSE 0 
                    END) as denied_claims
                FROM tebra.fin_claim_line cl
                {joins}
                WHERE 1=1
                {'AND cl.date_of_service >= :date_from' if date_from else ''}
                {'AND cl.date_of_service <= :date_to' if date_to else ''}
                GROUP BY {', '.join(group_by_clause)}
                HAVING COUNT(*) >= 5
            """)
            
            params = {}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            records = []
            for row in rows:
                total = row.total_claims or 0
                denied = row.denied_claims or 0
                denial_rate = float(denied / total) if total > 0 else 0.0
                
                group_key = {}
                for field in group_by:
                    if field in valid_group_by:
                        value = getattr(row, field, None)
                        if value:
                            group_key[field] = str(value)
                
                records.append(DenialRateRecord(
                    group_key=group_key,
                    total_claims=int(total),
                    denied_claims=int(denied),
                    denial_rate=denial_rate,
                    date_from=date_from,
                    date_to=date_to,
                ))
            
            logger.info("Retrieved historical denial rates", count=len(records), group_by=group_by)
            return records
    
    async def get_claim_line_items(self, claim_id: str) -> list[ClaimLineItem]:
        """Get line items for a claim.
        
        Now also fetches ICD-10 diagnosis codes from clin_encounter_diagnosis
        and place_of_service from clin_encounter.
        """
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    cl.tebra_claim_id as line_item_id,
                    cl.claim_reference_id as claim_id,
                    ROW_NUMBER() OVER (PARTITION BY cl.claim_reference_id 
                                       ORDER BY cl.date_of_service, cl.tebra_claim_id) as line_number,
                    cl.proc_code as cpt_code,
                    cl.date_of_service as service_date,
                    cl.billed_amount,
                    cl.paid_amount,
                    cl.units,
                    cl.modifiers_json,
                    e.place_of_service_code as place_of_service,
                    (SELECT string_agg(ed.diag_code, ',' ORDER BY ed.precedence)
                     FROM tebra.clin_encounter_diagnosis ed 
                     WHERE ed.encounter_id = cl.encounter_id
                     LIMIT 1) as icd10_codes
                FROM tebra.fin_claim_line cl
                LEFT JOIN tebra.clin_encounter e ON cl.encounter_id = e.encounter_id
                WHERE cl.claim_reference_id = :claim_id OR cl.tebra_claim_id = :claim_id
                ORDER BY cl.date_of_service, cl.tebra_claim_id
            """)
            
            result = await session.execute(query, {"claim_id": claim_id})
            rows = result.fetchall()
            
            line_items = []
            for row in rows:
                # Parse modifiers from JSON
                modifiers = []
                if row.modifiers_json:
                    try:
                        mods = json.loads(row.modifiers_json) if isinstance(row.modifiers_json, str) else row.modifiers_json
                        if isinstance(mods, list):
                            modifiers = [str(m) for m in mods]
                        elif isinstance(mods, dict):
                            modifiers = [str(v) for v in mods.values() if v]
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # Use first ICD-10 code from the encounter diagnosis list
                icd10_code = None
                if row.icd10_codes:
                    icd10_code = row.icd10_codes.split(',')[0].strip()
                
                line_items.append(ClaimLineItem(
                    line_item_id=row.line_item_id,
                    claim_id=row.claim_id or claim_id,
                    line_number=row.line_number or 1,
                    cpt_code=row.cpt_code,
                    modifiers=modifiers,
                    icd10_code=icd10_code,
                    units=Decimal(str(row.units or 1)),
                    billed_amount=Decimal(str(row.billed_amount or 0)),
                    place_of_service=row.place_of_service,
                    service_date=row.service_date,
                ))
            
            logger.info("Retrieved claim line items", claim_id=claim_id, count=len(line_items))
            return line_items
    
    async def close(self) -> None:
        """Close repository connections."""
        await self.engine.dispose()
        logger.info("Database repository closed")

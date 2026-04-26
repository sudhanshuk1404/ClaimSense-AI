"""API-layer request and response schemas.

These are separate from the domain models in src/models.py:
- src/models.py  → internal domain objects (EDI data, analysis outputs)
- api/schemas.py → HTTP request bodies and API-specific response envelopes

Keeping them separate lets the API contract evolve independently of the
internal model structure.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from src.models import (
    DenialAnalysis,
    PatternMatchResult,
    BatchIntelligenceReport,
    EDI835Claim,
    EDI837Claim,
)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class AnalyzeClaimRequest(BaseModel):
    """Body for POST /api/v1/claims/analyze — submit raw 835+837 data."""

    edi835: EDI835Claim = Field(..., description="EDI 835 remittance data for the denied claim")
    edi837: EDI837Claim = Field(..., description="EDI 837 original claim submission data")

    model_config = {
        "json_schema_extra": {
            "example": {
                "edi835": {
                    "pc_ClaimID": "CLM-2026-00142",
                    "pc_ClaimStatus": "4",
                    "pc_ClaimAmount": 4500.00,
                    "pc_ClaimPaid": 0.00,
                    "pc_InsuranceType": "Commercial",
                    "pc_ReceivedDate": "2026-03-20",
                    "cp_PayerName": "Blue Cross Blue Shield",
                    "pcla_AdjustmentGroup": "CO",
                    "pcla_AdjustmentReason": "29",
                    "pcla_AdjustmentAmount": 4500.00,
                    "pcl_ProcedureCode": "99214",
                },
                "edi837": {
                    "ec_ClaimNo": "CLM-2026-00142",
                    "ec_PayerName": "Blue Cross Blue Shield",
                    "ec_InsuranceType": "Commercial",
                    "ec_ServiceDateFrom": "2025-06-15",
                    "ec_PrincipalDiagnosis": "J06.9",
                    "ec_BillProvNPI": "1234567890",
                    "ec_DelayReasonCode": "",
                    "ec_ClaimFrequency": "1",
                },
            }
        }
    }


class PatternMatchRequest(BaseModel):
    """Body for POST /api/v1/patterns/match — submit a custom claim for pattern matching."""

    edi835: EDI835Claim
    edi837: EDI837Claim
    top_k: int = Field(default=5, ge=1, le=20, description="Number of similar claims to retrieve")


# ---------------------------------------------------------------------------
# Shared response envelope
# ---------------------------------------------------------------------------


class APIResponse(BaseModel):
    """Standard envelope wrapping every API response."""

    success: bool = True
    data: Any
    meta: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Claim summary (lightweight list view)
# ---------------------------------------------------------------------------


class ClaimSummary(BaseModel):
    """Lightweight claim representation for list endpoints."""

    claim_id: str
    outcome: str                          # "denied" | "paid"
    payer: Optional[str] = None
    procedure_code: Optional[str] = None
    insurance_type: Optional[str] = None
    claim_amount: float
    claim_paid: float
    carc_code: Optional[str] = None
    service_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Combined analysis response (Problem 1 + 2 together)
# ---------------------------------------------------------------------------


class FullClaimAnalysis(BaseModel):
    """Combined root-cause + pattern response returned by the analysis endpoints."""

    claim_id: str
    root_cause_analysis: DenialAnalysis
    pattern_match: Optional[PatternMatchResult] = None
    estimated_cost_usd: float = Field(
        default=0.0,
        description="Estimated OpenAI API cost for this analysis"
    )


# ---------------------------------------------------------------------------
# Batch request
# ---------------------------------------------------------------------------


class BatchRequest(BaseModel):
    """Optional body for POST /api/v1/batch/cluster — allows overriding the dataset."""

    claims: Optional[list[dict]] = Field(
        default=None,
        description="If provided, cluster these claims instead of the loaded dataset. "
                    "Each item must have 'edi835' and 'edi837' keys."
    )

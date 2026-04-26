"""Problem 1 — Claim Denial Root Cause Analysis endpoints.

Routes
------
GET  /api/v1/claims                    List all claims in the loaded dataset
GET  /api/v1/claims/{claim_id}         Fetch raw claim data by ID
GET  /api/v1/claims/{claim_id}/analyze Analyze a specific dataset claim (P1 + P2)
POST /api/v1/claims/analyze            Analyze a custom claim submitted in the body

Logic walkthrough (Problem 1)
------------------------------
1. Receive a denied claim (835 + 837 joined on claim_id).
2. Look up the CARC code in our local reference table to get domain context
   (category, typical recoverability, appeal notes).
3. Compute a derived field: days_from_service_to_received so the LLM doesn't
   have to do date arithmetic.
4. Build a detailed system prompt (prompts/denial_analysis.txt) that teaches
   the LLM the healthcare domain — CARC codes, group codes, timely filing
   windows, prior-auth rules.
5. Pass the full claim JSON + CARC context + derived fields to GPT-4o with
   JSON-mode enabled (response_format=json_object) to guarantee parseable output.
6. Validate the response through Pydantic: clamp confidence to [0,1], default
   invalid recoverability to "needs_review" so hallucinations can't crash the API.
7. Return a DenialAnalysis with: root_cause, carc_interpretation,
   recoverability verdict, confidence_score, supporting_evidence[], recommended_action.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.dependencies import (
    AppState,
    get_all_claims,
    get_analyzer,
    get_matcher,
    get_state,
)
from api.schemas import AnalyzeClaimRequest, ClaimSummary, FullClaimAnalysis
from src.data_loader import join_835_837
from src.denial_analyzer import DenialAnalyzer
from src.models import JoinedClaim
from src.pattern_matcher import PatternMatcher

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /claims — list dataset
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List all claims",
    description="Returns a lightweight summary of every claim in the loaded dataset.",
    response_model=list[ClaimSummary],
)
async def list_claims(
    outcome: str | None = Query(default=None, description="Filter by 'denied' or 'paid'"),
    payer: str | None = Query(default=None, description="Filter by payer name (case-insensitive substring)"),
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
):
    filtered = all_claims

    if outcome == "denied":
        filtered = [c for c in filtered if c.is_denied]
    elif outcome == "paid":
        filtered = [c for c in filtered if not c.is_denied]

    if payer:
        filtered = [c for c in filtered if c.payer_name and payer.lower() in c.payer_name.lower()]

    return [_to_summary(c) for c in filtered]


# ---------------------------------------------------------------------------
# GET /claims/{claim_id} — raw claim data
# ---------------------------------------------------------------------------


@router.get(
    "/{claim_id}",
    summary="Get claim by ID",
    description="Returns the raw joined 835+837 data for a specific claim from the dataset.",
)
async def get_claim(
    claim_id: str,
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
):
    claim = _find_claim(claim_id, all_claims)
    return {
        "claim_id": claim.claim_id,
        "outcome": "denied" if claim.is_denied else "paid",
        "edi835": claim.edi835.model_dump(exclude_none=True),
        "edi837": claim.edi837.model_dump(exclude_none=True),
    }


# ---------------------------------------------------------------------------
# GET /claims/{claim_id}/analyze — Problem 1 + 2 on a dataset claim
# ---------------------------------------------------------------------------


@router.get(
    "/{claim_id}/analyze",
    summary="Analyze a dataset claim (Problem 1 + 2)",
    description=(
        "Runs **root cause analysis** (Problem 1) and **historical pattern matching** "
        "(Problem 2) on a denied claim from the loaded dataset.\n\n"
        "**Problem 1 — Root Cause Analysis:**\n"
        "The LLM receives the full joined 835+837 payload plus enriched context "
        "(CARC reference data, days-since-service calculation) and reasons about "
        "WHY the claim was denied — going beyond the raw code to cite actual field "
        "values as evidence.\n\n"
        "**Problem 2 — Pattern Matching:**\n"
        "The denied claim is embedded and scored against all historical claims using "
        "a hybrid similarity metric (55% semantic embedding + 45% structured field "
        "matching on payer, procedure, insurance type, CARC, and diagnosis chapter). "
        "The LLM then interprets the retrieved similar claims to estimate the historical "
        "appeal success rate and identify systemic patterns."
    ),
    response_model=FullClaimAnalysis,
)
async def analyze_dataset_claim(
    claim_id: str,
    include_pattern: bool = Query(default=True, description="Also run pattern matching (Problem 2)"),
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
    analyzer: DenialAnalyzer = Depends(get_analyzer),
    matcher: PatternMatcher = Depends(get_matcher),
    state: AppState = Depends(get_state),
):
    claim = _find_claim(claim_id, all_claims)

    if not claim.is_denied:
        raise HTTPException(
            status_code=422,
            detail=f"Claim '{claim_id}' is not denied (status={claim.edi835.pc_ClaimStatus}). "
                   "Only denied claims can be analyzed.",
        )

    cost_before = state.llm.session_cost_usd

    # Run blocking LLM calls in a thread so the event loop stays free
    analysis = await asyncio.to_thread(analyzer.analyze, claim)

    pattern = None
    if include_pattern:
        pattern = await asyncio.to_thread(matcher.analyze, claim)

    cost_used = round(state.llm.session_cost_usd - cost_before, 6)

    return FullClaimAnalysis(
        claim_id=claim_id,
        root_cause_analysis=analysis,
        pattern_match=pattern,
        estimated_cost_usd=cost_used,
    )


# ---------------------------------------------------------------------------
# POST /claims/analyze — Problem 1 + 2 on a custom claim body
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    summary="Analyze a custom claim (Problem 1 + 2)",
    description=(
        "Submit your own 835+837 claim data and receive a full denial analysis.\n\n"
        "Identical logic to `GET /{claim_id}/analyze` but accepts any claim via "
        "the request body — useful for integrating with external billing systems "
        "without first loading data into the dataset.\n\n"
        "The claim must have `pc_ClaimStatus = '4'` (denied) in the 835 data."
    ),
    response_model=FullClaimAnalysis,
)
async def analyze_custom_claim(
    body: AnalyzeClaimRequest,
    include_pattern: bool = Query(default=True, description="Also run pattern matching (Problem 2)"),
    analyzer: DenialAnalyzer = Depends(get_analyzer),
    matcher: PatternMatcher = Depends(get_matcher),
    state: AppState = Depends(get_state),
):
    claim = join_835_837(
        body.edi835.model_dump(exclude_none=True),
        body.edi837.model_dump(exclude_none=True),
    )

    if not claim.is_denied:
        raise HTTPException(
            status_code=422,
            detail="The submitted claim is not denied (pc_ClaimStatus must be '4').",
        )

    cost_before = state.llm.session_cost_usd

    analysis = await asyncio.to_thread(analyzer.analyze, claim)

    pattern = None
    if include_pattern:
        pattern = await asyncio.to_thread(matcher.analyze, claim)

    cost_used = round(state.llm.session_cost_usd - cost_before, 6)

    return FullClaimAnalysis(
        claim_id=claim.claim_id,
        root_cause_analysis=analysis,
        pattern_match=pattern,
        estimated_cost_usd=cost_used,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_claim(claim_id: str, all_claims: list[JoinedClaim]) -> JoinedClaim:
    for c in all_claims:
        if c.claim_id == claim_id:
            return c
    raise HTTPException(
        status_code=404,
        detail=f"Claim '{claim_id}' not found in the loaded dataset.",
    )


def _to_summary(c: JoinedClaim) -> ClaimSummary:
    return ClaimSummary(
        claim_id=c.claim_id,
        outcome="denied" if c.is_denied else "paid",
        payer=c.payer_name,
        procedure_code=c.procedure_code,
        insurance_type=c.insurance_type,
        claim_amount=c.edi835.pc_ClaimAmount,
        claim_paid=c.edi835.pc_ClaimPaid,
        carc_code=c.carc_code,
        service_date=c.edi837.ec_ServiceDateFrom,
    )

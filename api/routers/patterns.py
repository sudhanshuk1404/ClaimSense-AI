"""Problem 2 — Historical Pattern Matching endpoints.

Routes
------
GET  /api/v1/patterns/{claim_id}   Pattern match a dataset claim against history
POST /api/v1/patterns/match        Pattern match a custom claim submitted in body
GET  /api/v1/patterns/stats        Denial statistics across the full dataset

Logic walkthrough (Problem 2)
------------------------------
The PatternMatcher uses a **hybrid two-stage similarity pipeline**:

Stage 1 — Embedding (semantic similarity, weight 55%)
  • Every claim is serialised to a flat text string containing payer, procedure
    code, diagnosis, insurance type, CARC code, and denial amount.
  • Each string is embedded using OpenAI text-embedding-3-small (1536 dims).
  • At startup the entire historical dataset is embedded and stored in memory
    (a lightweight in-process vector store).
  • For each query, the denied claim is embedded and cosine similarity is
    computed against all historical embeddings.  This captures semantic
    relationships that exact-match logic would miss (e.g. two different
    diagnosis codes that both indicate low-back pain).

Stage 2 — Structured field matching (weight 45%)
  • Five fields are compared with explicit weights:
      payer name       35 % — strongest predictor of payment behaviour
      procedure code   30 % — procedure + payer defines the billing context
      insurance type   15 % — Medicare vs Commercial changes all the rules
      CARC code        10 % — same denial category is a strong pattern signal
      diagnosis (3-char ICD prefix)  10 % — same disease chapter = similar case
  • Full exact match on all five = structural score of 1.0.

Combined score = 0.55 × cosine_similarity + 0.45 × structural_score

Why this weighting?
  Pure semantic embeddings can be fooled by claims that sound similar but
  involve different payers.  Pure structured matching misses nuance (e.g. two
  slightly different diagnoses for the same condition).  The hybrid gives us
  both interpretability (you can explain why a match was made) and recall
  (catches cases that exact matching would miss).

After retrieval the LLM receives:
  • The denied claim summary
  • The top-k similar claims with their outcomes (paid/denied) and match reasons
  • Aggregated denial stats: how often does this payer deny this procedure?

The LLM identifies:
  • A systemic pattern if it exists (e.g. "Aetna denies CPT 72148 without auth")
  • The historical appeal success rate derived from the retrieved paid/denied ratio
  • A narrative connecting the history to the appeal strategy
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import (
    AppState,
    get_all_claims,
    get_matcher,
    get_state,
)
from api.schemas import PatternMatchRequest
from src.data_loader import join_835_837
from src.models import JoinedClaim, PatternMatchResult
from src.pattern_matcher import PatternMatcher

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /patterns/{claim_id} — pattern match a dataset claim
# ---------------------------------------------------------------------------


@router.get(
    "/{claim_id}",
    summary="Pattern match a dataset claim (Problem 2)",
    description=(
        "Finds historically similar paid and denied claims for the specified denied claim.\n\n"
        "**How similarity is computed:**\n"
        "- **55% semantic** — OpenAI embedding cosine similarity on a flat-text "
        "representation of the claim (payer + procedure + diagnosis + amount + CARC)\n"
        "- **45% structural** — Weighted exact-field matching: payer (35%), "
        "procedure code (30%), insurance type (15%), CARC code (10%), "
        "diagnosis ICD chapter (10%)\n\n"
        "The LLM then interprets the retrieved claims to identify systemic patterns "
        "and estimate the historical appeal success rate."
    ),
    response_model=PatternMatchResult,
)
async def pattern_match_dataset_claim(
    claim_id: str,
    top_k: int = Query(default=5, ge=1, le=20, description="Number of similar claims to retrieve"),
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
    matcher: PatternMatcher = Depends(get_matcher),
    state: AppState = Depends(get_state),
):
    claim = _find_claim(claim_id, all_claims)

    if not claim.is_denied:
        raise HTTPException(
            status_code=422,
            detail=f"Claim '{claim_id}' is not denied. Only denied claims can be pattern matched.",
        )

    # Override top_k if caller requested a different number
    original_top_k = matcher._top_k
    matcher._top_k = top_k

    result = await asyncio.to_thread(matcher.analyze, claim)

    matcher._top_k = original_top_k  # restore
    return result


# ---------------------------------------------------------------------------
# POST /patterns/match — pattern match a custom claim
# ---------------------------------------------------------------------------


@router.post(
    "/match",
    summary="Pattern match a custom claim (Problem 2)",
    description=(
        "Submit your own 835+837 denied claim and receive historical pattern analysis.\n\n"
        "Identical matching logic to `GET /{claim_id}` but accepts any claim body — "
        "useful when the claim isn't in the loaded dataset."
    ),
    response_model=PatternMatchResult,
)
async def pattern_match_custom_claim(
    body: PatternMatchRequest,
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

    original_top_k = matcher._top_k
    matcher._top_k = body.top_k

    result = await asyncio.to_thread(matcher.analyze, claim)

    matcher._top_k = original_top_k
    return result


# ---------------------------------------------------------------------------
# GET /patterns/stats — dataset-wide denial statistics
# ---------------------------------------------------------------------------


@router.get(
    "/stats/overview",
    summary="Denial statistics across the dataset",
    description=(
        "Returns aggregated denial statistics across the full loaded dataset: "
        "denial rates by payer, by CARC code, and by procedure — useful for "
        "identifying systemic patterns without running an LLM call."
    ),
)
async def denial_stats(
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
):
    denied = [c for c in all_claims if c.is_denied]
    paid   = [c for c in all_claims if not c.is_denied]

    # By payer
    by_payer: dict[str, dict] = defaultdict(lambda: {"denied": 0, "paid": 0, "total_denied_amount": 0.0})
    for c in denied:
        key = c.payer_name or "Unknown"
        by_payer[key]["denied"] += 1
        by_payer[key]["total_denied_amount"] += c.denial_amount
    for c in paid:
        key = c.payer_name or "Unknown"
        by_payer[key]["paid"] += 1

    payer_stats = []
    for payer, counts in by_payer.items():
        total = counts["denied"] + counts["paid"]
        payer_stats.append({
            "payer": payer,
            "total_claims": total,
            "denied": counts["denied"],
            "paid": counts["paid"],
            "denial_rate": round(counts["denied"] / total, 2) if total else 0.0,
            "total_denied_amount": round(counts["total_denied_amount"], 2),
        })
    payer_stats.sort(key=lambda x: x["denied"], reverse=True)

    # By CARC code
    by_carc: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_amount": 0.0})
    for c in denied:
        key = c.carc_code or "Unknown"
        by_carc[key]["count"] += 1
        by_carc[key]["total_amount"] += c.denial_amount

    carc_stats = sorted(
        [{"carc_code": k, **v} for k, v in by_carc.items()],
        key=lambda x: x["total_amount"],
        reverse=True,
    )

    # By procedure
    by_proc: dict[str, dict] = defaultdict(lambda: {"denied": 0, "paid": 0})
    for c in denied:
        if c.procedure_code:
            by_proc[c.procedure_code]["denied"] += 1
    for c in paid:
        if c.procedure_code:
            by_proc[c.procedure_code]["paid"] += 1

    proc_stats = sorted(
        [{"procedure_code": k, **v} for k, v in by_proc.items()],
        key=lambda x: x["denied"],
        reverse=True,
    )

    return {
        "summary": {
            "total_claims": len(all_claims),
            "total_denied": len(denied),
            "total_paid": len(paid),
            "overall_denial_rate": round(len(denied) / len(all_claims), 2) if all_claims else 0.0,
            "total_denied_amount": round(sum(c.denial_amount for c in denied), 2),
        },
        "by_payer": payer_stats,
        "by_carc_code": carc_stats,
        "by_procedure_code": proc_stats,
    }


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

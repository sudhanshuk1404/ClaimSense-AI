"""Problem 3 — Denial Clustering & Batch Intelligence endpoints.

Routes
------
GET  /api/v1/batch/cluster          Run clustering on all denied claims in dataset
POST /api/v1/batch/cluster          Run clustering on a custom set of claims
GET  /api/v1/batch/clusters/{id}    Get a specific cluster detail

Logic walkthrough (Problem 3)
------------------------------
Billing teams don't work claim-by-claim — they have hundreds of denials to
process and need to know WHERE to focus first.  The BatchClusterer solves this
in four steps:

Step 1 — Rule-based primary clustering (payer + CARC code)
  • Every denied claim is assigned to a group keyed by "<payer>|CARC-<code>".
  • Example groups: "Aetna|CARC-197", "Blue Cross|CARC-29", "Cigna|CARC-16".
  • Why rule-based first?  Because billing teams need INTERPRETABLE clusters.
    "Aetna prior-auth denials" is immediately actionable.  "Cluster #4" is not.
  • This gives us high-signal, domain-grounded groupings with zero ML cost.

Step 2 — Semantic sub-clustering (K-means on embeddings, for large groups)
  • If a rule-based group has ≥5 claims, we sub-cluster it using K-means
    on the OpenAI embeddings of each claim's text representation.
  • This splits heterogeneous groups further — e.g. "Aetna CARC-29" might
    contain both very old timely-filing misses (unrecoverable) and edge cases
    where a secondary-payer EOB exists (potentially recoverable).  K-means
    separates them so the billing team gets distinct action items.
  • Number of sub-clusters = min(3, group_size // 2) to avoid over-fragmentation.

Step 3 — Appeal rate estimation
  • For each cluster, we look up historical claims with the same payer + CARC
    and compute:  paid_count / total_matching_historical_claims.
  • This is the "baseline" — before any appeal is filed.
  • Falls back to payer-only if no payer+CARC historical data exists.

Step 4 — LLM enrichment (single batch call, not per-cluster)
  • All clusters are sent in ONE LLM call to minimise cost and latency.
  • The LLM receives: cluster metadata, claim counts, denied amounts,
    procedure codes, historical appeal rate, and 3 representative sample claims.
  • The LLM returns: human-readable label, billing-team-ready summary,
    specific recommended action, and a priority (high/medium/low).
  • One call for N clusters is far cheaper than N separate calls.

Step 5 — Top opportunity selection
  • Each cluster is scored: denied_amount × adjusted_appeal_rate.
  • CARC codes are given a recoverability multiplier:
      High: 16 (missing info), 197 (prior auth), 252 (documentation), 22 (COB)
      Low:  18 (duplicate), 97 (bundling)
  • The cluster with the highest score is flagged as the top opportunity —
    the single place where billing effort yields the most revenue.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import (
    AppState,
    get_all_claims,
    get_clusterer,
    get_denied_claims_dep,
    get_state,
)
from api.schemas import BatchRequest
from src.batch_clusterer import BatchClusterer
from src.data_loader import load_claims_from_dicts, get_denied_claims
from src.models import BatchIntelligenceReport, DenialCluster, JoinedClaim

router = APIRouter()

# Cache the last batch report so repeated GETs don't re-run the expensive LLM call
_cached_report: BatchIntelligenceReport | None = None


# ---------------------------------------------------------------------------
# GET /batch/cluster — run on the loaded dataset
# ---------------------------------------------------------------------------


@router.get(
    "/cluster",
    summary="Batch cluster all denied claims (Problem 3)",
    description=(
        "Groups all denied claims in the loaded dataset into actionable clusters "
        "and produces a batch intelligence report for the billing team.\n\n"
        "**Clustering pipeline:**\n"
        "1. **Rule-based** — group by `payer + CARC code` (interpretable, zero ML cost)\n"
        "2. **Semantic sub-clustering** — K-means on OpenAI embeddings for groups ≥5 "
        "(splits heterogeneous groups by procedure/diagnosis patterns)\n"
        "3. **Appeal rate estimation** — compute paid/denied ratio from historical data\n"
        "4. **LLM enrichment** — ONE batch call generates labels, summaries, "
        "recommended actions, and priorities for all clusters\n"
        "5. **Top opportunity** — scored by `denied_amount × adjusted_recoverability`\n\n"
        "Results are cached — use `?refresh=true` to force a re-run."
    ),
    response_model=BatchIntelligenceReport,
)
async def cluster_dataset(
    refresh: bool = False,
    denied_claims: list[JoinedClaim] = Depends(get_denied_claims_dep),
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
    clusterer: BatchClusterer = Depends(get_clusterer),
):
    global _cached_report

    if _cached_report is not None and not refresh:
        return _cached_report

    if not denied_claims:
        raise HTTPException(status_code=422, detail="No denied claims found in the dataset.")

    report = await asyncio.to_thread(
        clusterer.analyze_batch,
        denied_claims,
        all_claims,
    )

    _cached_report = report
    return report


# ---------------------------------------------------------------------------
# POST /batch/cluster — run on a custom set of claims
# ---------------------------------------------------------------------------


@router.post(
    "/cluster",
    summary="Batch cluster custom claims (Problem 3)",
    description=(
        "Submit your own list of claims (mix of paid and denied) and receive "
        "a batch intelligence report.\n\n"
        "Each item in `claims` must have `'edi835'` and `'edi837'` keys matching "
        "the EDI835Claim and EDI837Claim schemas. "
        "Only claims with `pc_ClaimStatus='4'` (denied) will be clustered; "
        "paid claims serve as the historical baseline for appeal rate estimation."
    ),
    response_model=BatchIntelligenceReport,
)
async def cluster_custom_claims(
    body: BatchRequest,
    clusterer: BatchClusterer = Depends(get_clusterer),
    all_claims: list[JoinedClaim] = Depends(get_all_claims),
):
    if not body.claims:
        raise HTTPException(
            status_code=422,
            detail="'claims' must be a non-empty list of claim objects.",
        )

    try:
        parsed = load_claims_from_dicts(body.claims)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    denied = get_denied_claims(parsed)
    if not denied:
        raise HTTPException(
            status_code=422,
            detail="No denied claims (pc_ClaimStatus='4') found in the submitted list.",
        )

    # Use the submitted claims as history; fall back to the loaded dataset
    historical = parsed if len(parsed) > len(denied) else all_claims

    report = await asyncio.to_thread(
        clusterer.analyze_batch,
        denied,
        historical,
    )
    return report


# ---------------------------------------------------------------------------
# GET /batch/clusters/{cluster_id} — detail for one cluster
# ---------------------------------------------------------------------------


@router.get(
    "/clusters/{cluster_id}",
    summary="Get cluster detail",
    description=(
        "Returns the full detail for a single cluster from the last batch run. "
        "Call `GET /batch/cluster` first to populate the cache."
    ),
    response_model=DenialCluster,
)
async def get_cluster(cluster_id: str):
    global _cached_report

    if _cached_report is None:
        raise HTTPException(
            status_code=404,
            detail="No batch report available yet. Call GET /api/v1/batch/cluster first.",
        )

    for cluster in _cached_report.clusters:
        if cluster.cluster_id == cluster_id:
            return cluster

    raise HTTPException(
        status_code=404,
        detail=f"Cluster '{cluster_id}' not found. Available IDs: "
               + ", ".join(c.cluster_id for c in _cached_report.clusters),
    )

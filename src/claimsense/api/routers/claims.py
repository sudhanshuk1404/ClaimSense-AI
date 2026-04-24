from fastapi import APIRouter, Request

from claimsense.clustering.clusterer import cluster_analyses
from claimsense.ingestion.loaders import load_claim835, load_claim837, load_historical_claims
from claimsense.normalization.claim_joiner import join_claims
from claimsense.reasoning.schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    ClaimAnalysisRequest,
    ClaimAnalysisResponse,
    DenialCluster,
    EvidenceItem,
)

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


@router.post("/analyze", response_model=ClaimAnalysisResponse)
def analyze_claim(payload: ClaimAnalysisRequest, request: Request) -> ClaimAnalysisResponse:
    claim_837 = load_claim837(payload.claim_837.model_dump(mode="python"))
    claim_835 = load_claim835(payload.claim_835.model_dump(mode="python"))
    historical_claims = load_historical_claims([item.model_dump(mode="python") for item in payload.historical_claims])
    unified_claim = join_claims(claim_837, claim_835)
    unified_analysis = request.app.state.orchestrator.analyze(unified_claim, historical_claims)
    unified_analysis.supporting_evidence.append(
        EvidenceItem(
            field="denied_amount",
            value=unified_claim.denied_amount,
            why_it_matters="Denied dollars drive work-queue prioritization.",
        )
    )
    return ClaimAnalysisResponse.model_validate(unified_analysis)


@router.post("/batch/analyze", response_model=BatchAnalysisResponse)
def analyze_batch(payload: BatchAnalysisRequest, request: Request) -> BatchAnalysisResponse:
    analyses = [analyze_claim(item, request) for item in payload.claims]
    clusters = cluster_analyses(analyses)
    return BatchAnalysisResponse(analyses=analyses, clusters=clusters)


@router.post("/clusters", response_model=list[DenialCluster])
def cluster_claims(analyses: list[ClaimAnalysisResponse]) -> list[DenialCluster]:
    return cluster_analyses(analyses)

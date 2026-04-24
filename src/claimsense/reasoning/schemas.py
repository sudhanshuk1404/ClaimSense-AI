from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from claimsense.ingestion.models import Claim835Record, Claim837Record, HistoricalClaim


class EvidenceItem(BaseModel):
    field: str
    value: Any
    why_it_matters: str


class RuleResult(BaseModel):
    rule: str
    result: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    score_impact: float = 0.0


class SimilarClaim(BaseModel):
    claim_id: str
    similarity_score: float
    outcome: str
    appeal_success: bool = False


class HistoricalContext(BaseModel):
    similar_claims_found: int = 0
    paid_similarity_rate: float = 0.0
    appeal_success_rate: float = 0.0


class CodeDescriptor(BaseModel):
    code: str
    meaning: str


class ClaimAnalysisRequest(BaseModel):
    claim_837: Claim837Record
    claim_835: Claim835Record
    historical_claims: list[HistoricalClaim] = Field(default_factory=list)


class ClaimAnalysisResponse(BaseModel):
    claim_id: str
    denial_category: str
    carc: CodeDescriptor
    rarc: list[CodeDescriptor] = Field(default_factory=list)
    root_cause: str
    recoverability_verdict: Literal["recoverable", "needs_review", "not_recoverable"]
    confidence: float
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    historical_context: HistoricalContext
    recommended_action: str
    rule_results: list[RuleResult] = Field(default_factory=list)
    similar_claims: list[SimilarClaim] = Field(default_factory=list)
    narrative: str


class BatchAnalysisRequest(BaseModel):
    claims: list[ClaimAnalysisRequest]


class DenialCluster(BaseModel):
    cluster_id: str
    summary: str
    claim_count: int
    total_denied_amount: float
    estimated_recoverable_amount: float
    historical_appeal_success_rate: float
    recommended_work_queue_priority: Literal["high", "medium", "low"]


class BatchAnalysisResponse(BaseModel):
    analyses: list[ClaimAnalysisResponse]
    clusters: list[DenialCluster]


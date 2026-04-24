from __future__ import annotations

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.reasoning.schemas import HistoricalContext, SimilarClaim
from claimsense.similarity.feature_similarity import top_similar_claims
from claimsense.similarity.vector_index import NarrativeVectorIndex


class SimilarityRetriever:
    def __init__(self, historical_claims: list[HistoricalClaim]) -> None:
        self.historical_claims = historical_claims
        self.vector_index = NarrativeVectorIndex(historical_claims)

    def retrieve(self, claim: UnifiedClaim, limit: int = 5) -> tuple[list[SimilarClaim], HistoricalContext]:
        structured = top_similar_claims(claim, self.historical_claims, limit=limit)
        semantic_scores = dict(self.vector_index.search(claim, limit=limit * 2))

        blended: list[SimilarClaim] = []
        for item in structured:
            blended_score = round((item.similarity_score * 0.8) + (semantic_scores.get(item.claim_id, 0.0) * 0.2), 4)
            blended.append(item.model_copy(update={"similarity_score": blended_score}))

        similar_claims = sorted(blended, key=lambda candidate: candidate.similarity_score, reverse=True)[:limit]
        paid = [item for item in similar_claims if item.outcome == "paid"]
        successful_appeals = [item for item in similar_claims if item.appeal_success]
        historical_context = HistoricalContext(
            similar_claims_found=len(similar_claims),
            paid_similarity_rate=round(len(paid) / len(similar_claims), 2) if similar_claims else 0.0,
            appeal_success_rate=round(len(successful_appeals) / len(similar_claims), 2) if similar_claims else 0.0,
        )
        return similar_claims, historical_context


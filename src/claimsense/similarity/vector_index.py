from __future__ import annotations

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.normalization.feature_builder import build_claim_narrative


class NarrativeVectorIndex:
    """Token-overlap fallback for local development until a real embedding store is attached."""

    def __init__(self, historical_claims: list[HistoricalClaim]) -> None:
        self.documents = {claim.claim_id: self._tokenize(self._historical_narrative(claim)) for claim in historical_claims}
        self.historical_claims = {claim.claim_id: claim for claim in historical_claims}

    def _tokenize(self, text: str) -> set[str]:
        return {token.strip(".,").lower() for token in text.split() if token}

    def _historical_narrative(self, claim: HistoricalClaim) -> str:
        return (
            f"{claim.payer} {claim.insurance_type} claim for CPT {', '.join(claim.procedure_codes)} "
            f"diagnoses {', '.join(claim.diagnosis_codes)} provider {claim.provider_npi} "
            f"prior auth {'present' if claim.prior_auth_present else 'missing'} denial {', '.join(claim.denial_codes)}."
        )

    def search(self, claim: UnifiedClaim, limit: int = 5) -> list[tuple[str, float]]:
        claim_tokens = self._tokenize(build_claim_narrative(claim))
        scores: list[tuple[str, float]] = []
        for claim_id, tokens in self.documents.items():
            intersection = len(claim_tokens & tokens)
            union = len(claim_tokens | tokens) or 1
            scores.append((claim_id, round(intersection / union, 4)))
        return sorted(scores, key=lambda item: item[1], reverse=True)[:limit]


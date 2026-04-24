from __future__ import annotations

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.reasoning.schemas import SimilarClaim
from claimsense.normalization.feature_builder import extract_procedure_codes


WEIGHTS = {
    "payer": 0.20,
    "procedure": 0.20,
    "diagnosis": 0.15,
    "modifier": 0.10,
    "provider": 0.10,
    "pos": 0.05,
    "prior_auth": 0.05,
    "amount": 0.05,
    "denial_code": 0.05,
    "date": 0.05,
}


def _overlap_score(values_a: set[str], values_b: set[str]) -> float:
    if not values_a and not values_b:
        return 1.0
    if not values_a or not values_b:
        return 0.0
    return len(values_a & values_b) / len(values_a | values_b)


def score_claim_similarity(claim: UnifiedClaim, historical: HistoricalClaim) -> float:
    procedure_score = _overlap_score(set(extract_procedure_codes(claim)), set(historical.procedure_codes))
    diagnosis_score = _overlap_score(set(claim.diagnosis_codes), set(historical.diagnosis_codes))
    modifier_score = _overlap_score(
        {modifier for line in claim.procedure_lines for modifier in line.modifiers},
        set(historical.modifiers),
    )
    amount_gap = abs(claim.claim_amount - historical.claim_amount)
    amount_score = max(0.0, 1 - amount_gap / max(claim.claim_amount, historical.claim_amount, 1))
    date_gap = abs((claim.service_date_from - historical.service_date_from).days)
    date_score = max(0.0, 1 - min(date_gap, 365) / 365)

    total = 0.0
    total += WEIGHTS["payer"] if claim.payer == historical.payer else 0.0
    total += WEIGHTS["procedure"] * procedure_score
    total += WEIGHTS["diagnosis"] * diagnosis_score
    total += WEIGHTS["modifier"] * modifier_score
    total += WEIGHTS["provider"] if claim.provider_npi == historical.provider_npi else 0.0
    total += WEIGHTS["pos"] if any(line.place_of_service == historical.place_of_service for line in claim.procedure_lines) else 0.0
    total += WEIGHTS["prior_auth"] if bool(claim.prior_auth) == historical.prior_auth_present else 0.0
    total += WEIGHTS["amount"] * amount_score
    total += WEIGHTS["denial_code"] * _overlap_score(set(claim.adjustment_codes), set(historical.denial_codes))
    total += WEIGHTS["date"] * date_score
    return round(total, 4)


def top_similar_claims(
    claim: UnifiedClaim,
    historical_claims: list[HistoricalClaim],
    limit: int = 5,
) -> list[SimilarClaim]:
    scored = sorted(
        (
            SimilarClaim(
                claim_id=item.claim_id,
                similarity_score=score_claim_similarity(claim, item),
                outcome=item.outcome,
                appeal_success=item.appeal_success,
            )
            for item in historical_claims
        ),
        key=lambda candidate: candidate.similarity_score,
        reverse=True,
    )
    return scored[:limit]


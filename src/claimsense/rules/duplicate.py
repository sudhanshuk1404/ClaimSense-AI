from __future__ import annotations

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.reasoning.schemas import EvidenceItem, RuleResult


class DuplicateClaimRule:
    name = "duplicate_claim_check"

    def __init__(self, historical_claims: list[HistoricalClaim]) -> None:
        self.historical_claims = historical_claims

    def evaluate(self, claim: UnifiedClaim) -> RuleResult:
        if not {"18", "97"} & set(claim.adjustment_codes):
            return RuleResult(rule=self.name, result="not_applicable", evidence=[])

        procedure_codes = {line.procedure_code for line in claim.procedure_lines}
        for historical in self.historical_claims:
            same_party = (
                (claim.patient_id and historical.patient_id == claim.patient_id)
                or (claim.subscriber_id and historical.subscriber_id == claim.subscriber_id)
            )
            same_core_claim = (
                historical.claim_id != claim.claim_id
                and historical.payer == claim.payer
                and historical.provider_npi == claim.provider_npi
                and historical.service_date_from == claim.service_date_from
                and set(historical.procedure_codes) == procedure_codes
            )
            if same_party and same_core_claim:
                return RuleResult(
                    rule=self.name,
                    result="likely_duplicate",
                    evidence=[
                        EvidenceItem(
                            field="historical_claim_id",
                            value=historical.claim_id,
                            why_it_matters="A prior claim with the same payer, provider, date, and procedures suggests duplication.",
                        )
                    ],
                    score_impact=-0.3,
                )

        return RuleResult(rule=self.name, result="needs_review", evidence=[], score_impact=-0.05)

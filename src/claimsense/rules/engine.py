from __future__ import annotations

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.reasoning.schemas import RuleResult
from claimsense.rules.duplicate import DuplicateClaimRule
from claimsense.rules.medical_necessity import MedicalNecessityRule
from claimsense.rules.missing_info import MissingInformationRule
from claimsense.rules.timely_filing import TimelyFilingRule


class RulesEngine:
    def __init__(
        self,
        payer_rules: dict[str, dict[str, int | bool | str]],
        historical_claims: list[HistoricalClaim] | None = None,
    ) -> None:
        self.rules = [
            TimelyFilingRule(payer_rules),
            MissingInformationRule(),
            MedicalNecessityRule(),
            DuplicateClaimRule(historical_claims or []),
        ]

    def run(self, claim: UnifiedClaim) -> list[RuleResult]:
        return [rule.evaluate(claim) for rule in self.rules]


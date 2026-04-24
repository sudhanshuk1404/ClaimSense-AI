from __future__ import annotations

from claimsense.ingestion.models import UnifiedClaim
from claimsense.reasoning.schemas import EvidenceItem, RuleResult


class TimelyFilingRule:
    name = "timely_filing_check"

    def __init__(self, payer_rules: dict[str, dict[str, int | bool | str]]) -> None:
        self.payer_rules = payer_rules

    def evaluate(self, claim: UnifiedClaim) -> RuleResult:
        if "29" not in claim.adjustment_codes:
            return RuleResult(rule=self.name, result="not_applicable", evidence=[])

        if not claim.received_date:
            return RuleResult(
                rule=self.name,
                result="needs_review",
                evidence=[
                    EvidenceItem(
                        field="received_date",
                        value=None,
                        why_it_matters="Timely filing cannot be confirmed without payer receipt date.",
                    )
                ],
                score_impact=-0.05,
            )

        payer_policy = self.payer_rules.get(claim.payer) or self.payer_rules.get("Commercial_Default", {})
        timely_days = int(payer_policy.get("timely_filing_days") or payer_policy.get("timely_filing_days_max", 180))
        days_elapsed = (claim.received_date - claim.service_date_from).days
        result = "likely_valid_denial" if days_elapsed > timely_days else "likely_overturned"
        score_impact = -0.35 if result == "likely_valid_denial" else 0.2

        return RuleResult(
            rule=self.name,
            result=result,
            evidence=[
                EvidenceItem(
                    field="service_date_from",
                    value=str(claim.service_date_from),
                    why_it_matters="Timely filing is measured from the date of service.",
                ),
                EvidenceItem(
                    field="received_date",
                    value=str(claim.received_date),
                    why_it_matters="Receipt date determines the filing window.",
                ),
                EvidenceItem(
                    field="days_elapsed",
                    value=days_elapsed,
                    why_it_matters="Elapsed days are compared against payer filing limits.",
                ),
            ],
            score_impact=score_impact,
        )


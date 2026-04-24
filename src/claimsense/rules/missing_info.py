from __future__ import annotations

from claimsense.ingestion.models import UnifiedClaim
from claimsense.reasoning.schemas import EvidenceItem, RuleResult


class MissingInformationRule:
    name = "missing_information_check"

    def evaluate(self, claim: UnifiedClaim) -> RuleResult:
        if not {"16", "252"} & set(claim.adjustment_codes):
            return RuleResult(rule=self.name, result="not_applicable", evidence=[])

        evidence: list[EvidenceItem] = []
        missing_fields: list[str] = []

        if not claim.prior_auth:
            missing_fields.append("prior_auth")
            evidence.append(
                EvidenceItem(
                    field="prior_auth",
                    value="",
                    why_it_matters="Missing prior authorization is a common fixable denial driver.",
                )
            )

        if any(not line.diagnosis_pointers for line in claim.procedure_lines):
            missing_fields.append("diagnosis_pointers")
            evidence.append(
                EvidenceItem(
                    field="diagnosis_pointers",
                    value=[],
                    why_it_matters="Procedure lines without diagnosis pointers can trigger missing information denials.",
                )
            )

        result = "fixable_missing_info" if missing_fields else "needs_review"
        return RuleResult(rule=self.name, result=result, evidence=evidence, score_impact=0.22 if missing_fields else 0.0)


from __future__ import annotations

from claimsense.ingestion.models import UnifiedClaim
from claimsense.reasoning.schemas import EvidenceItem, RuleResult


HIGH_SCRUTINY_CPTS = {"72148", "72158", "70553", "73721"}
SUPPORTIVE_DIAGNOSES = {"M51.16", "M54.16", "M48.061", "R29.898"}


class MedicalNecessityRule:
    name = "medical_necessity_check"

    def evaluate(self, claim: UnifiedClaim) -> RuleResult:
        if "50" not in claim.adjustment_codes:
            return RuleResult(rule=self.name, result="not_applicable", evidence=[])

        procedure_codes = {line.procedure_code for line in claim.procedure_lines}
        diagnosis_codes = set(claim.diagnosis_codes)
        supportive_match = bool(diagnosis_codes & SUPPORTIVE_DIAGNOSES)
        high_scrutiny_match = bool(procedure_codes & HIGH_SCRUTINY_CPTS)

        evidence = [
            EvidenceItem(
                field="procedure_codes",
                value=sorted(procedure_codes),
                why_it_matters="High-cost imaging and specialty procedures often require stronger documentation.",
            ),
            EvidenceItem(
                field="diagnosis_codes",
                value=sorted(diagnosis_codes),
                why_it_matters="Diagnosis support is reviewed for medical necessity denials.",
            ),
            EvidenceItem(
                field="prior_auth",
                value=claim.prior_auth or "",
                why_it_matters="Missing authorization reduces medical necessity recoverability.",
            ),
        ]

        if high_scrutiny_match and not claim.prior_auth:
            return RuleResult(
                rule=self.name,
                result="likely_documentation_gap",
                evidence=evidence,
                score_impact=0.08 if supportive_match else -0.08,
            )

        return RuleResult(
            rule=self.name,
            result="appeal_possible" if supportive_match else "likely_valid_denial",
            evidence=evidence,
            score_impact=0.18 if supportive_match else -0.15,
        )


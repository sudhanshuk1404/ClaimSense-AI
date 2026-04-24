from __future__ import annotations

from claimsense.ingestion.models import UnifiedClaim


def build_claim_narrative(claim: UnifiedClaim) -> str:
    procedure_codes = ", ".join(line.procedure_code for line in claim.procedure_lines)
    diagnosis_codes = ", ".join(claim.diagnosis_codes) or "none"
    modifiers = sorted({modifier for line in claim.procedure_lines for modifier in line.modifiers})
    modifier_text = ", ".join(modifiers) if modifiers else "none"
    prior_auth = "present" if claim.prior_auth else "missing"
    denial_codes = ", ".join(claim.adjustment_codes) or "none"
    return (
        f"{claim.payer} {claim.insurance_type} claim for CPT {procedure_codes}, diagnoses {diagnosis_codes}, "
        f"provider {claim.provider_npi}, modifiers {modifier_text}, prior authorization {prior_auth}, "
        f"denied with CARC {denial_codes}."
    )


def extract_procedure_codes(claim: UnifiedClaim) -> list[str]:
    return [line.procedure_code for line in claim.procedure_lines]


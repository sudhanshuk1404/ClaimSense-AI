from claimsense.ingestion.models import HistoricalClaim, ProcedureLine, UnifiedClaim
from claimsense.rules.duplicate import DuplicateClaimRule


def test_duplicate_rule_finds_matching_historical_claim():
    claim = UnifiedClaim(
        claim_id="NEW-1",
        payer="Aetna",
        insurance_type="commercial",
        claim_amount=220,
        paid_amount=0,
        denied_amount=220,
        service_date_from="2026-02-10",
        service_date_to="2026-02-10",
        received_date="2026-02-12",
        diagnosis_codes=["I10"],
        procedure_lines=[ProcedureLine(line_id="1", procedure_code="99213", charge_amount=220)],
        adjustment_codes=["18"],
        remark_codes=[],
        provider_npi="1234567890",
        patient_id="PAT-1",
        subscriber_id="SUB-1",
    )
    historical = HistoricalClaim(
        claim_id="OLD-1",
        payer="Aetna",
        insurance_type="commercial",
        procedure_codes=["99213"],
        diagnosis_codes=["I10"],
        provider_npi="1234567890",
        service_date_from="2026-02-10",
        prior_auth_present=False,
        claim_amount=220,
        denial_codes=["18"],
        patient_id="PAT-1",
        subscriber_id="SUB-1",
        outcome="paid",
    )
    result = DuplicateClaimRule([historical]).evaluate(claim)
    assert result.result == "likely_duplicate"


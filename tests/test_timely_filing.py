from claimsense.ingestion.models import UnifiedClaim, ProcedureLine
from claimsense.rules.timely_filing import TimelyFilingRule


def test_timely_filing_rule_marks_claim_not_recoverable_when_late():
    claim = UnifiedClaim(
        claim_id="CLM-1",
        payer="Aetna",
        insurance_type="commercial",
        claim_amount=100,
        paid_amount=0,
        denied_amount=100,
        service_date_from="2025-01-01",
        service_date_to="2025-01-01",
        received_date="2025-08-01",
        diagnosis_codes=["I10"],
        procedure_lines=[ProcedureLine(line_id="1", procedure_code="99213", charge_amount=100)],
        adjustment_codes=["29"],
        remark_codes=[],
        provider_npi="123",
    )
    result = TimelyFilingRule({"Aetna": {"timely_filing_days": 180}}).evaluate(claim)
    assert result.result == "likely_valid_denial"
    assert result.score_impact < 0


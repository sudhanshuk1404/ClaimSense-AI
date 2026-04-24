from claimsense.ingestion.models import HistoricalClaim, ProcedureLine, UnifiedClaim
from claimsense.similarity.feature_similarity import score_claim_similarity


def test_similarity_rewards_exact_payer_procedure_matches():
    claim = UnifiedClaim(
        claim_id="CLM-1",
        payer="Aetna",
        insurance_type="commercial",
        claim_amount=1000,
        paid_amount=0,
        denied_amount=1000,
        service_date_from="2026-01-10",
        service_date_to="2026-01-10",
        received_date="2026-01-15",
        diagnosis_codes=["M54.5", "M51.16"],
        procedure_lines=[
            ProcedureLine(line_id="1", procedure_code="72148", modifiers=["26"], charge_amount=1000, place_of_service="11")
        ],
        adjustment_codes=["50"],
        remark_codes=["N386"],
        provider_npi="1234567890",
        prior_auth=None,
    )
    historical = HistoricalClaim(
        claim_id="H-1",
        payer="Aetna",
        insurance_type="commercial",
        procedure_codes=["72148"],
        diagnosis_codes=["M51.16"],
        provider_npi="1234567890",
        service_date_from="2026-01-12",
        place_of_service="11",
        modifiers=["26"],
        prior_auth_present=False,
        claim_amount=1000,
        denial_codes=["50"],
        outcome="paid",
    )
    assert score_claim_similarity(claim, historical) > 0.7


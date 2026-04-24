from claimsense.ingestion.models import Claim835Record, Claim837Record, HistoricalClaim, ProcedureLine
from claimsense.normalization.claim_joiner import join_claims
from claimsense.reasoning.orchestrator import ClaimAnalysisOrchestrator, KnowledgeBase


def main() -> None:
    orchestrator = ClaimAnalysisOrchestrator(KnowledgeBase(knowledge_dir="knowledge"))
    claim_837 = Claim837Record(
        claim_id="CLM-2026-00391",
        payer="Aetna",
        insurance_type="commercial",
        claim_amount=1400,
        service_date_from="2026-02-10",
        received_date="2026-02-20",
        diagnosis_codes=["M54.5", "M51.16"],
        procedure_lines=[
            ProcedureLine(
                line_id="1",
                procedure_code="72148",
                modifiers=[],
                diagnosis_pointers=["1", "2"],
                charge_amount=1400,
                place_of_service="11",
            )
        ],
        provider_npi="1234567890",
        prior_auth=None,
        claim_frequency="1",
        patient_id="PAT-1",
        subscriber_id="SUB-1",
    )
    claim_835 = Claim835Record(
        claim_id="CLM-2026-00391",
        paid_amount=0,
        denied_amount=1400,
        adjustment_codes=["50"],
        remark_codes=["N386"],
    )
    historical_claims = [
        HistoricalClaim(
            claim_id="HIST-100",
            payer="Aetna",
            insurance_type="commercial",
            procedure_codes=["72148"],
            diagnosis_codes=["M51.16"],
            provider_npi="1234567890",
            service_date_from="2026-01-22",
            place_of_service="11",
            prior_auth_present=True,
            claim_amount=1325,
            denial_codes=["50"],
            patient_id="PAT-X",
            subscriber_id="SUB-X",
            outcome="paid",
            appeal_success=True,
        )
    ]

    unified = join_claims(claim_837, claim_835)
    response = orchestrator.analyze(unified, historical_claims)
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()


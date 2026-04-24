from claimsense.clustering.clusterer import cluster_analyses
from claimsense.ingestion.models import Claim835Record, Claim837Record, ProcedureLine
from claimsense.normalization.claim_joiner import join_claims
from claimsense.reasoning.orchestrator import ClaimAnalysisOrchestrator, KnowledgeBase


def build_claim(claim_id: str, adjustment_code: str, denied_amount: float) -> tuple[Claim837Record, Claim835Record]:
    claim_837 = Claim837Record(
        claim_id=claim_id,
        payer="Aetna",
        insurance_type="commercial",
        claim_amount=denied_amount,
        service_date_from="2026-02-10",
        received_date="2026-02-20",
        diagnosis_codes=["M54.5", "M51.16"],
        procedure_lines=[
            ProcedureLine(
                line_id="1",
                procedure_code="72148",
                modifiers=[],
                diagnosis_pointers=["1", "2"],
                charge_amount=denied_amount,
                place_of_service="11",
            )
        ],
        provider_npi="1234567890",
        prior_auth=None,
        claim_frequency="1",
        patient_id=f"PAT-{claim_id}",
        subscriber_id=f"SUB-{claim_id}",
    )
    claim_835 = Claim835Record(
        claim_id=claim_id,
        paid_amount=0,
        denied_amount=denied_amount,
        adjustment_codes=[adjustment_code],
        remark_codes=["N386"],
    )
    return claim_837, claim_835


def main() -> None:
    orchestrator = ClaimAnalysisOrchestrator(KnowledgeBase(knowledge_dir="knowledge"))
    analyses = []
    for claim_id, adjustment_code, denied_amount in [
        ("CLM-1", "50", 1400),
        ("CLM-2", "50", 1650),
        ("CLM-3", "16", 950),
    ]:
        claim_837, claim_835 = build_claim(claim_id, adjustment_code, denied_amount)
        analysis = orchestrator.analyze(join_claims(claim_837, claim_835), historical_claims=[])
        analysis.supporting_evidence.append(
            {"field": "denied_amount", "value": denied_amount, "why_it_matters": "Used for prioritization."}
        )
        analyses.append(analysis)

    response = cluster_analyses(analyses)
    for cluster in response:
        print(cluster.model_dump_json(indent=2))


if __name__ == "__main__":
    main()


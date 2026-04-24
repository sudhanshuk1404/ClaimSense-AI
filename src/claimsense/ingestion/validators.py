from claimsense.ingestion.models import Claim835Record, Claim837Record


def validate_claim_pair(claim_837: Claim837Record, claim_835: Claim835Record) -> None:
    if claim_837.claim_id != claim_835.claim_id:
        raise ValueError("835 and 837 claim_id values must match before analysis.")

    if not claim_837.procedure_lines:
        raise ValueError("837 claim must contain at least one procedure line.")


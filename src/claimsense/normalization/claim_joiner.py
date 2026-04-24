from claimsense.ingestion.models import Claim835Record, Claim837Record, UnifiedClaim
from claimsense.ingestion.validators import validate_claim_pair


def join_claims(claim_837: Claim837Record, claim_835: Claim835Record) -> UnifiedClaim:
    validate_claim_pair(claim_837, claim_835)
    return UnifiedClaim(
        claim_id=claim_837.claim_id,
        payer=claim_837.payer,
        insurance_type=claim_837.insurance_type,
        claim_amount=claim_837.claim_amount,
        paid_amount=claim_835.paid_amount,
        denied_amount=claim_835.denied_amount,
        service_date_from=claim_837.service_date_from,
        service_date_to=claim_837.service_date_end,
        received_date=claim_837.received_date,
        diagnosis_codes=claim_837.diagnosis_codes,
        procedure_lines=claim_837.procedure_lines,
        adjustment_codes=claim_835.adjustment_codes,
        remark_codes=claim_835.remark_codes,
        provider_npi=claim_837.provider_npi,
        prior_auth=claim_837.prior_auth,
        claim_frequency=claim_837.claim_frequency,
        patient_id=claim_837.patient_id,
        subscriber_id=claim_837.subscriber_id,
        type_of_bill=claim_837.type_of_bill,
        raw_835=claim_835.raw_835,
        raw_837=claim_837.raw_837,
    )


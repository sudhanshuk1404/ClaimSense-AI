from fastapi.testclient import TestClient

from claimsense.api.main import create_app


def test_claim_analysis_endpoint_returns_valid_schema():
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/claims/analyze",
        json={
            "claim_837": {
                "claim_id": "CLM-2026-00391",
                "payer": "Aetna",
                "insurance_type": "commercial",
                "claim_amount": 1400,
                "service_date_from": "2026-02-10",
                "received_date": "2026-02-20",
                "diagnosis_codes": ["M54.5", "M51.16"],
                "procedure_lines": [
                    {
                        "line_id": "1",
                        "procedure_code": "72148",
                        "modifiers": [],
                        "diagnosis_pointers": ["1", "2"],
                        "charge_amount": 1400,
                        "place_of_service": "11",
                    }
                ],
                "provider_npi": "1234567890",
                "prior_auth": "",
                "claim_frequency": "1",
                "patient_id": "PAT-1",
                "subscriber_id": "SUB-1",
            },
            "claim_835": {
                "claim_id": "CLM-2026-00391",
                "paid_amount": 0,
                "denied_amount": 1400,
                "adjustment_codes": ["50"],
                "remark_codes": ["N386"],
            },
            "historical_claims": [],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["claim_id"] == "CLM-2026-00391"
    assert "recoverability_verdict" in body
    assert body["carc"]["code"] == "50"


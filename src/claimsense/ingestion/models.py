from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, computed_field


class ProcedureLine(BaseModel):
    line_id: str
    procedure_code: str
    modifiers: list[str] = Field(default_factory=list)
    diagnosis_pointers: list[str] = Field(default_factory=list)
    charge_amount: float
    allowed_amount: float | None = None
    paid_amount: float | None = None
    units: int = 1
    place_of_service: str | None = None


class AdjustmentLine(BaseModel):
    group_code: str | None = None
    adjustment_code: str
    amount: float = 0.0
    remark_codes: list[str] = Field(default_factory=list)


class Claim837Record(BaseModel):
    claim_id: str
    payer: str
    insurance_type: str
    claim_amount: float
    service_date_from: date
    service_date_to: date | None = None
    received_date: date | None = None
    diagnosis_codes: list[str] = Field(default_factory=list)
    procedure_lines: list[ProcedureLine] = Field(default_factory=list)
    provider_npi: str
    prior_auth: str | None = None
    claim_frequency: str | None = None
    patient_id: str | None = None
    subscriber_id: str | None = None
    type_of_bill: str | None = None
    raw_837: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def service_date_end(self) -> date:
        return self.service_date_to or self.service_date_from


class Claim835Record(BaseModel):
    claim_id: str
    paid_amount: float
    denied_amount: float
    adjustment_codes: list[str] = Field(default_factory=list)
    remark_codes: list[str] = Field(default_factory=list)
    adjustment_lines: list[AdjustmentLine] = Field(default_factory=list)
    processed_date: date | None = None
    raw_835: dict[str, Any] = Field(default_factory=dict)


class HistoricalClaim(BaseModel):
    claim_id: str
    payer: str
    insurance_type: str
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)
    provider_npi: str
    service_date_from: date
    place_of_service: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    prior_auth_present: bool = False
    claim_amount: float = 0.0
    denial_codes: list[str] = Field(default_factory=list)
    patient_id: str | None = None
    subscriber_id: str | None = None
    outcome: str
    appeal_success: bool = False


class UnifiedClaim(BaseModel):
    claim_id: str
    payer: str
    insurance_type: str
    claim_amount: float
    paid_amount: float
    denied_amount: float
    service_date_from: date
    service_date_to: date
    received_date: date | None = None
    diagnosis_codes: list[str] = Field(default_factory=list)
    procedure_lines: list[ProcedureLine] = Field(default_factory=list)
    adjustment_codes: list[str] = Field(default_factory=list)
    remark_codes: list[str] = Field(default_factory=list)
    provider_npi: str
    prior_auth: str | None = None
    claim_frequency: str | None = None
    patient_id: str | None = None
    subscriber_id: str | None = None
    type_of_bill: str | None = None
    raw_835: dict[str, Any] = Field(default_factory=dict)
    raw_837: dict[str, Any] = Field(default_factory=dict)

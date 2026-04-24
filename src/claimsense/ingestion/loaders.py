from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claimsense.ingestion.models import Claim835Record, Claim837Record, HistoricalClaim


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def load_claim837(payload: dict[str, Any]) -> Claim837Record:
    return Claim837Record.model_validate(payload)


def load_claim835(payload: dict[str, Any]) -> Claim835Record:
    return Claim835Record.model_validate(payload)


def load_historical_claims(payload: list[dict[str, Any]]) -> list[HistoricalClaim]:
    return [HistoricalClaim.model_validate(item) for item in payload]


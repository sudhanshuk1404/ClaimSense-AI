from __future__ import annotations

from typing import Protocol

from claimsense.ingestion.models import UnifiedClaim
from claimsense.reasoning.schemas import RuleResult


class RuleCheck(Protocol):
    name: str

    def evaluate(self, claim: UnifiedClaim) -> RuleResult:
        ...


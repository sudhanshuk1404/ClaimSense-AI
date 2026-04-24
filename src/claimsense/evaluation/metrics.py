from __future__ import annotations

from claimsense.reasoning.schemas import ClaimAnalysisResponse


def json_validity_rate(results: list[ClaimAnalysisResponse]) -> float:
    if not results:
        return 0.0
    valid = sum(1 for result in results if result.model_dump())
    return round(valid / len(results), 2)


def evidence_precision(results: list[ClaimAnalysisResponse]) -> float:
    if not results:
        return 0.0
    with_evidence = sum(1 for result in results if result.supporting_evidence)
    return round(with_evidence / len(results), 2)


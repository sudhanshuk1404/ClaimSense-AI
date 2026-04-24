from claimsense.reasoning.schemas import ClaimAnalysisResponse


def recoverability_accuracy(
    predictions: list[ClaimAnalysisResponse],
    expected: dict[str, str],
) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for item in predictions if expected.get(item.claim_id) == item.recoverability_verdict)
    return round(correct / len(predictions), 2)


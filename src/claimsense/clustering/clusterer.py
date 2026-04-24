from __future__ import annotations

from collections import defaultdict

from claimsense.reasoning.schemas import ClaimAnalysisResponse, DenialCluster


def cluster_analyses(analyses: list[ClaimAnalysisResponse]) -> list[DenialCluster]:
    grouped: dict[str, list[ClaimAnalysisResponse]] = defaultdict(list)
    for analysis in analyses:
        key = f"{analysis.carc.code}_{analysis.denial_category}_{analysis.recoverability_verdict}"
        grouped[key].append(analysis)

    clusters: list[DenialCluster] = []
    for key, items in grouped.items():
        total_denied = round(sum(extract_denied_amount(item) for item in items), 2)
        recoverable_amount = round(
            sum(extract_denied_amount(item) * item.confidence for item in items if item.recoverability_verdict != "not_recoverable"),
            2,
        )
        appeal_rate = round(
            sum(item.historical_context.appeal_success_rate for item in items) / len(items),
            2,
        )
        priority = work_queue_priority(total_denied, recoverable_amount)
        clusters.append(
            DenialCluster(
                cluster_id=key,
                summary=f"{len(items)} claims in the {items[0].denial_category} cluster with CARC {items[0].carc.code}.",
                claim_count=len(items),
                total_denied_amount=total_denied,
                estimated_recoverable_amount=recoverable_amount,
                historical_appeal_success_rate=appeal_rate,
                recommended_work_queue_priority=priority,
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.estimated_recoverable_amount, reverse=True)


def extract_denied_amount(analysis: ClaimAnalysisResponse) -> float:
    for item in analysis.supporting_evidence:
        if item.field == "denied_amount":
            try:
                return float(item.value)
            except (TypeError, ValueError):
                continue
    return 0.0


def work_queue_priority(total_denied_amount: float, estimated_recoverable_amount: float) -> str:
    if estimated_recoverable_amount >= 50000 or total_denied_amount >= 100000:
        return "high"
    if estimated_recoverable_amount >= 10000:
        return "medium"
    return "low"

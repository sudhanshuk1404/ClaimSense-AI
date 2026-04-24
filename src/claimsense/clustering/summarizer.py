from claimsense.reasoning.schemas import DenialCluster


def summarize_cluster(cluster: DenialCluster) -> str:
    return (
        f"{cluster.summary} Total denied amount is {cluster.total_denied_amount:.2f} with "
        f"estimated recoverable amount {cluster.estimated_recoverable_amount:.2f}."
    )


from __future__ import annotations

from claimsense.ingestion.models import UnifiedClaim
from claimsense.reasoning.schemas import HistoricalContext, RuleResult, SimilarClaim


class ReasoningClient:
    """Deterministic local fallback that preserves the interface for a future LLM adapter."""

    def generate_explanation(
        self,
        claim: UnifiedClaim,
        denial_category: str,
        rule_results: list[RuleResult],
        similar_claims: list[SimilarClaim],
        historical_context: HistoricalContext,
    ) -> tuple[str, str]:
        meaningful_rules = [rule for rule in rule_results if rule.result not in {"not_applicable", "needs_review"}]
        drivers = ", ".join(rule.result for rule in meaningful_rules[:2]) or "claim-level denial indicators"
        similar_summary = (
            f"{historical_context.similar_claims_found} similar claims were found with "
            f"{historical_context.appeal_success_rate:.0%} appeal success."
            if historical_context.similar_claims_found
            else "No closely similar historical claims were found."
        )
        root_cause = (
            f"The payer denied this claim in the {denial_category} category based on {drivers}. "
            f"{similar_summary}"
        )
        action = _recommended_action(denial_category, claim.prior_auth, similar_claims)
        return root_cause, action


def _recommended_action(denial_category: str, prior_auth: str | None, similar_claims: list[SimilarClaim]) -> str:
    if denial_category == "timely_filing":
        return "Validate filing dates, payer receipt records, and any accepted delay reason before pursuing reconsideration."
    if denial_category == "duplicate":
        return "Confirm whether an earlier paid or replacement claim exists before rebilling or appealing."
    if denial_category == "medical_necessity":
        if not prior_auth:
            return "Review payer policy, confirm whether prior authorization was required, and appeal with supporting clinical documentation if available."
        return "Appeal with medical records, diagnosis support, and payer policy citations showing clinical necessity."
    if denial_category == "missing_information":
        return "Correct the missing fields, regenerate the claim, and resubmit with complete documentation."
    if similar_claims and any(item.appeal_success for item in similar_claims):
        return "Review the most similar successfully appealed claims and mirror the supporting evidence package."
    return "Route to analyst review with the cited evidence before further payer action."


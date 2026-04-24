from __future__ import annotations

from pathlib import Path

import yaml

from claimsense.ingestion.models import HistoricalClaim, UnifiedClaim
from claimsense.normalization.feature_builder import build_claim_narrative
from claimsense.reasoning.llm_client import ReasoningClient
from claimsense.reasoning.schemas import (
    ClaimAnalysisResponse,
    CodeDescriptor,
    HistoricalContext,
)
from claimsense.rules.engine import RulesEngine
from claimsense.similarity.retriever import SimilarityRetriever


DEFAULT_CARC = {"16": "Claim/service lacks information", "18": "Duplicate claim", "29": "Timely filing limit exceeded", "50": "Non-covered because not deemed medically necessary", "97": "Payment adjusted because benefit already included"}
DEFAULT_RARC = {"N386": "Additional documentation or medical necessity review may apply"}


class KnowledgeBase:
    def __init__(self, knowledge_dir: Path | str) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.carc_catalog = self._load_yaml("carc_catalog.yaml") or DEFAULT_CARC
        self.rarc_catalog = self._load_yaml("rarc_catalog.yaml") or DEFAULT_RARC
        self.payer_rules = self._load_yaml("payer_rules.yaml") or {}
        self.denial_playbooks = self._load_yaml("denial_playbooks.yaml") or {}

    def _load_yaml(self, filename: str) -> dict:
        path = self.knowledge_dir / filename
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}


class ClaimAnalysisOrchestrator:
    def __init__(self, knowledge_base: KnowledgeBase, reasoning_client: ReasoningClient | None = None) -> None:
        self.knowledge_base = knowledge_base
        self.reasoning_client = reasoning_client or ReasoningClient()

    def analyze(self, claim: UnifiedClaim, historical_claims: list[HistoricalClaim]) -> ClaimAnalysisResponse:
        rules_engine = RulesEngine(self.knowledge_base.payer_rules, historical_claims)
        rule_results = rules_engine.run(claim)
        similarity_retriever = SimilarityRetriever(historical_claims)
        similar_claims, historical_context = similarity_retriever.retrieve(claim)

        denial_category = determine_denial_category(claim.adjustment_codes)
        confidence = score_recoverability(claim, rule_results, historical_context)
        verdict = map_confidence_to_verdict(confidence)
        carc = primary_carc(claim.adjustment_codes, self.knowledge_base.carc_catalog)
        rarc = resolve_rarcs(claim.remark_codes, self.knowledge_base.rarc_catalog)
        root_cause, recommended_action = self.reasoning_client.generate_explanation(
            claim=claim,
            denial_category=denial_category,
            rule_results=rule_results,
            similar_claims=similar_claims,
            historical_context=historical_context,
        )

        supporting_evidence = []
        for result in rule_results:
            supporting_evidence.extend(result.evidence)

        return ClaimAnalysisResponse(
            claim_id=claim.claim_id,
            denial_category=denial_category,
            carc=carc,
            rarc=rarc,
            root_cause=root_cause,
            recoverability_verdict=verdict,
            confidence=confidence,
            supporting_evidence=deduplicate_evidence(supporting_evidence),
            historical_context=historical_context,
            recommended_action=recommended_action,
            rule_results=rule_results,
            similar_claims=similar_claims,
            narrative=build_claim_narrative(claim),
        )


def determine_denial_category(adjustment_codes: list[str]) -> str:
    if "29" in adjustment_codes:
        return "timely_filing"
    if "50" in adjustment_codes:
        return "medical_necessity"
    if {"18", "97"} & set(adjustment_codes):
        return "duplicate"
    if {"16", "252"} & set(adjustment_codes):
        return "missing_information"
    return "other"


def primary_carc(adjustment_codes: list[str], catalog: dict[str, str]) -> CodeDescriptor:
    code = adjustment_codes[0] if adjustment_codes else "unknown"
    return CodeDescriptor(code=code, meaning=catalog.get(code, "Unmapped CARC code"))


def resolve_rarcs(remark_codes: list[str], catalog: dict[str, str]) -> list[CodeDescriptor]:
    return [CodeDescriptor(code=code, meaning=catalog.get(code, "Unmapped RARC code")) for code in remark_codes]


def score_recoverability(claim: UnifiedClaim, rule_results: list, historical_context: HistoricalContext) -> float:
    base_score = {
        "50": 0.55,
        "16": 0.65,
        "18": 0.20,
        "29": 0.15,
        "97": 0.20,
    }.get(claim.adjustment_codes[0] if claim.adjustment_codes else "", 0.45)
    score = base_score + sum(result.score_impact for result in rule_results)
    score += historical_context.paid_similarity_rate * 0.1
    score += historical_context.appeal_success_rate * 0.15
    if not claim.prior_auth and "50" in claim.adjustment_codes:
        score -= 0.08
    return round(max(0.0, min(score, 1.0)), 2)


def map_confidence_to_verdict(confidence: float) -> str:
    if confidence >= 0.75:
        return "recoverable"
    if confidence >= 0.45:
        return "needs_review"
    return "not_recoverable"


def deduplicate_evidence(evidence: list) -> list:
    seen: set[tuple[str, str]] = set()
    unique = []
    for item in evidence:
        key = (item.field, str(item.value))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique

"""Main orchestration pipeline for ClaimSense AI.

Ties together all three analysis modules:
- Problem 1: DenialAnalyzer  — root cause per claim
- Problem 2: PatternMatcher  — historical pattern matching
- Problem 3: BatchClusterer  — denial clustering & batch intelligence
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .batch_clusterer import BatchClusterer
from .data_loader import get_denied_claims, get_paid_claims, load_carc_reference, load_claims_from_file
from .denial_analyzer import DenialAnalyzer
from .llm_client import LLMClient
from .models import (
    BatchIntelligenceReport,
    DenialAnalysis,
    JoinedClaim,
    PatternMatchResult,
)
from .pattern_matcher import PatternMatcher


@dataclass
class PipelineResult:
    """Full output of a pipeline run."""

    analyzed_claims: list[DenialAnalysis] = field(default_factory=list)
    pattern_results: list[PatternMatchResult] = field(default_factory=list)
    batch_report: Optional[BatchIntelligenceReport] = None
    session_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "analyzed_claims": [a.model_dump() for a in self.analyzed_claims],
            "pattern_results": [p.model_dump() for p in self.pattern_results],
            "batch_report": self.batch_report.model_dump() if self.batch_report else None,
            "session_cost_usd": round(self.session_cost_usd, 6),
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))


class ClaimSensePipeline:
    """End-to-end pipeline: load → analyze → pattern match → cluster → report."""

    def __init__(self, model: str = "gpt-4o", embedding_model: str = "text-embedding-3-small") -> None:
        self._llm = LLMClient(model=model, embedding_model=embedding_model)
        self._analyzer = DenialAnalyzer(self._llm)
        self._matcher = PatternMatcher(self._llm, top_k=5)
        self._clusterer = BatchClusterer(self._llm)

    # ------------------------------------------------------------------
    # High-level entry points
    # ------------------------------------------------------------------

    def run_from_file(
        self,
        data_path: str | Path = "data/synthetic_claims.json",
        run_analysis: bool = True,
        run_pattern_matching: bool = True,
        run_batch: bool = True,
        single_claim_id: Optional[str] = None,
    ) -> PipelineResult:
        """Load claims from file and run the full (or partial) pipeline."""
        all_claims = load_claims_from_file(data_path)
        return self.run(
            all_claims=all_claims,
            run_analysis=run_analysis,
            run_pattern_matching=run_pattern_matching,
            run_batch=run_batch,
            single_claim_id=single_claim_id,
        )

    def run(
        self,
        all_claims: list[JoinedClaim],
        run_analysis: bool = True,
        run_pattern_matching: bool = True,
        run_batch: bool = True,
        single_claim_id: Optional[str] = None,
    ) -> PipelineResult:
        """Run the pipeline on a list of pre-loaded claims."""
        denied = get_denied_claims(all_claims)
        paid = get_paid_claims(all_claims)

        if single_claim_id:
            target_denied = [c for c in denied if c.claim_id == single_claim_id]
        else:
            target_denied = denied

        result = PipelineResult()

        # ---- Problem 1: Root cause analysis --------------------------
        if run_analysis and target_denied:
            result.analyzed_claims = self._analyzer.analyze_batch(target_denied)

        # ---- Problem 2: Pattern matching ------------------------------
        if run_pattern_matching and target_denied:
            # Index the full historical set (paid + denied, minus the ones being analyzed)
            self._matcher.index_claims(all_claims)
            for claim in target_denied:
                pm = self._matcher.analyze(claim)
                result.pattern_results.append(pm)

        # ---- Problem 3: Batch clustering & intelligence ---------------
        if run_batch and denied:
            result.batch_report = self._clusterer.analyze_batch(
                denied_claims=denied,
                historical_claims=all_claims,
            )

        result.session_cost_usd = self._llm.session_cost_usd
        return result

    def analyze_single_claim(
        self, edi835: dict, edi837: dict
    ) -> tuple[DenialAnalysis, PatternMatchResult]:
        """Convenience: analyze a single claim given raw 835+837 dicts."""
        from .data_loader import join_835_837, load_claims_from_file

        claim = join_835_837(edi835, edi837)
        if not claim.is_denied:
            raise ValueError(f"Claim {claim.claim_id} is not denied.")

        analysis = self._analyzer.analyze(claim)

        # Index all synthetic claims as history
        historical = load_claims_from_file()
        self._matcher.index_claims(historical)
        pattern = self._matcher.analyze(claim)

        return analysis, pattern

"""Investigation orchestrator - single entry point for the full investigation pipeline."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.investigation.evidence_collector import EvidenceCollector, EvidenceCollection
from src.investigation.hypothesis_generator import Hypothesis, HypothesisGenerator
from src.investigation.hypothesis_ranker import HypothesisRanker
from src.investigation.investigation_planner import InvestigationPlan, InvestigationPlanner
from src.investigation.recommendation_engine import Recommendation, RecommendationEngine
from src.investigation.report_generator import InvestigationReport, ReportGenerator
from src.investigation.root_cause_engine import RootCauseEngine, RootCauseResult

logger = logging.getLogger(__name__)


class InvestigationOrchestrator:
    """Orchestrates the full investigation pipeline.

    Pipeline flow:
        1. Plan       → InvestigationPlanner.analyze_question()
        2. Collect    → EvidenceCollector.collect_evidence()
        3. Hypothesize → HypothesisGenerator.generate_hypotheses()
        4. Rank       → HypothesisRanker.rank_hypotheses()
        5. Root cause → RootCauseEngine.determine_root_cause()
        6. Recommend  → RecommendationEngine.generate_recommendations()
        7. Report     → ReportGenerator.generate_report()

    Usage:
        orchestrator = InvestigationOrchestrator()
        report = orchestrator.investigate("Why is campaign C123 underdelivering?")
    """

    def __init__(self, db_session: Optional[Session] = None) -> None:
        """Initialise the orchestrator with optional pre-existing DB session."""
        self._session = db_session
        self._planner = InvestigationPlanner()
        self._evidence_collector: Optional[EvidenceCollector] = None
        self._hypothesis_generator = HypothesisGenerator()
        self._hypothesis_ranker = HypothesisRanker()
        self._root_cause_engine = RootCauseEngine()
        self._recommendation_engine = RecommendationEngine()
        self._report_generator = ReportGenerator()

    def investigate(self, question: str) -> InvestigationReport:
        """Run the full investigation pipeline on a natural-language question.

        Args:
            question: Natural-language question about ad operations, e.g.
                      *"Why is campaign C123 underdelivering?"*

        Returns:
            InvestigationReport with all findings, evidence, and recommendations.
        """
        # ── Step 1: Plan ───────────────────────────────────────────
        logger.info("Step 1/7: Planning investigation for question")
        plan = self._safe_plan(question)
        logger.info("  Issue type: %s | Entities: %d | Steps: %d",
                     plan.issue_type, len(plan.entities), len(plan.steps))

        # ── Step 2: Collect evidence ───────────────────────────────
        logger.info("Step 2/7: Collecting evidence")
        evidence_collection = self._safe_collect(plan)
        logger.info("  Evidence items collected: %d", evidence_collection.total_metrics)

        # ── Step 3: Generate hypotheses ────────────────────────────
        logger.info("Step 3/7: Generating hypotheses")
        hypotheses = self._safe_hypothesize(evidence_collection)
        logger.info("  Hypotheses generated: %d", len(hypotheses))

        # ── Step 4: Rank hypotheses ────────────────────────────────
        logger.info("Step 4/7: Ranking hypotheses")
        ranked = self._safe_rank(hypotheses, evidence_collection)
        logger.info("  Top hypothesis: %s (confidence=%.4f)",
                     ranked[0].category if ranked else "none",
                     ranked[0].confidence if ranked else 0.0)

        # ── Step 5: Determine root cause ───────────────────────────
        logger.info("Step 5/7: Determining root cause")
        root_cause = self._safe_root_cause(ranked, evidence_collection)
        logger.info("  Primary cause: %s (confidence=%.4f)",
                     root_cause.primary_category, root_cause.confidence)

        # ── Step 6: Generate recommendations ───────────────────────
        logger.info("Step 6/7: Generating recommendations")
        recommendations = self._safe_recommend(root_cause, evidence_collection)
        logger.info("  Recommendations generated: %d", len(recommendations))

        # ── Step 7: Generate report ────────────────────────────────
        logger.info("Step 7/7: Generating report")
        report = self._safe_report(question, root_cause, recommendations, evidence_collection)
        logger.info("Report complete: %s | risk=%s | confidence=%.4f",
                     report.report_id, report.risk_level, report.confidence)

        return report

    # ── Safe wrappers (catch errors at each step) ──────────────────────

    def _safe_plan(self, question: str) -> InvestigationPlan:
        try:
            return self._planner.analyze_question(question)
        except Exception as exc:
            logger.error("Planner failed: %s", exc)
            from src.investigation.investigation_planner import InvestigationPlan, TimeRange
            return InvestigationPlan(
                issue_type="general",
                entities=[],
                time_range=TimeRange(start="unknown", end="unknown", relative="unknown"),
                steps=[],
                raw_question=question,
            )

    def _safe_collect(self, plan: InvestigationPlan) -> EvidenceCollection:
        try:
            if self._evidence_collector is None:
                self._evidence_collector = EvidenceCollector(db_session=self._session)
            return self._evidence_collector.collect_evidence(plan)
        except Exception as exc:
            logger.error("Evidence collector failed: %s", exc)
            return EvidenceCollection(plan=plan, evidence_items=[], total_metrics=0)

    def _safe_hypothesize(self, evidence_collection: EvidenceCollection) -> List[Hypothesis]:
        try:
            return self._hypothesis_generator.generate_hypotheses(evidence_collection)
        except Exception as exc:
            logger.error("Hypothesis generator failed: %s", exc)
            return [
                Hypothesis(
                    hypothesis_id="H00",
                    description="Hypothesis generation failed due to an internal error.",
                    evidence_refs=[],
                    confidence=0.0,
                    category="general",
                )
            ]

    def _safe_rank(
        self, hypotheses: List[Hypothesis], evidence_collection: EvidenceCollection
    ) -> List[Hypothesis]:
        try:
            return self._hypothesis_ranker.rank_hypotheses(hypotheses, evidence_collection)
        except Exception as exc:
            logger.error("Hypothesis ranker failed: %s", exc)
            return hypotheses  # Return unranked as fallback

    def _safe_root_cause(
        self, hypotheses: List[Hypothesis], evidence_collection: EvidenceCollection
    ) -> RootCauseResult:
        try:
            return self._root_cause_engine.determine_root_cause(hypotheses, evidence_collection)
        except Exception as exc:
            logger.error("Root cause engine failed: %s", exc)
            return RootCauseResult(
                primary_cause="Root cause analysis failed due to an internal error.",
                confidence=0.0,
                contributing_factors=[str(exc)],
                evidence_summary="",
                supporting_metrics={},
                primary_category="general",
            )

    def _safe_recommend(
        self, root_cause: RootCauseResult, evidence_collection: EvidenceCollection
    ) -> List[Recommendation]:
        try:
            return self._recommendation_engine.generate_recommendations(
                root_cause, evidence_collection
            )
        except Exception as exc:
            logger.error("Recommendation engine failed: %s", exc)
            return [
                Recommendation(
                    action="Manual review required: recommendation engine encountered an error.",
                    expected_impact="N/A",
                    priority="medium",
                    type="general",
                )
            ]

    def _safe_report(
        self,
        question: str,
        root_cause: RootCauseResult,
        recommendations: List[Recommendation],
        evidence_collection: EvidenceCollection,
    ) -> InvestigationReport:
        try:
            return self._report_generator.generate_report(
                question, root_cause, recommendations, evidence_collection
            )
        except Exception as exc:
            logger.error("Report generator failed: %s", exc)
            return InvestigationReport(
                summary=f"Report generation failed for: {question[:100]}",
                primary_cause="Error during report generation.",
                confidence=0.0,
                evidence_table=[],
                supporting_factors=[],
                recommendations=[],
                risk_level="medium",
                report_id="ERROR",
                generated_at="",
            )

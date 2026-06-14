"""Script to run evaluation against the AdOps Copilot agent pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run AdOps Copilot evaluation")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("questions.json"),
        help="Path to questions.json file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation_report.html"),
        help="Output path for HTML report",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Pass threshold score (0.0-1.0)",
    )
    parser.add_argument(
        "--pipeline",
        choices=["mock", "live"],
        default="mock",
        help="Pipeline type to evaluate",
    )
    args = parser.parse_args()

    if args.pipeline == "live":
        logger.info("Live pipeline evaluation not implemented, using mock pipeline")
        pipeline = MockPipeline()
    else:
        pipeline = MockPipeline()

    from evaluation import Evaluator

    evaluator = Evaluator(
        pipeline=pipeline,
        questions_path=args.questions,
        output_path=args.output,
        threshold=args.threshold,
    )

    logger.info("Starting evaluation with %s pipeline", args.pipeline)
    results = evaluator.run()

    summary = evaluator.get_summary()
    logger.info("Evaluation complete:")
    for key, value in summary.items():
        logger.info("  %s: %s", key, value)

    report_path = evaluator.generate_report()
    logger.info("Report generated: %s", report_path)

    failed = summary.get("failed", 0)
    if failed > 0:
        logger.warning("%d questions failed evaluation", failed)
        sys.exit(1)

    sys.exit(0)


class MockPipeline:
    """Mock agent pipeline for evaluation testing."""

    def retrieve(self, query: str) -> list[dict]:
        """Mock retrieval returning sample documents."""
        return [
            {
                "id": "doc_001",
                "content": f"Ad performance data for query: {query}. "
                "Campaign shows 15% increase in ROAS over last 30 days.",
                "score": 0.92,
            },
            {
                "id": "doc_002",
                "content": "Budget allocation recommendations based on historical data "
                "suggest shifting 20% from display to search campaigns.",
                "score": 0.85,
            },
            {
                "id": "doc_003",
                "content": "Keyword analysis reveals top performers have CTR above 3.5%. "
                "Consider pausing keywords with CTR below 0.5%.",
                "score": 0.78,
            },
        ]

    def analyze(self, query: str, context: list[dict]) -> dict:
        """Mock analysis producing an answer."""
        context_text = " ".join(doc.get("content", "") for doc in context[:2])
        answer = (
            f"Based on the retrieved data: {context_text[:150]}... "
            "Recommendations: Increase budget for high-performing campaigns, "
            "pause underperforming keywords, and reallocate spend to search channels."
        )
        return {"answer": answer, "confidence": 0.87}


if __name__ == "__main__":
    main()

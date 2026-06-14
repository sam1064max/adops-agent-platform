"""Evaluation framework for AdOps Copilot agent pipeline."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class AgentPipeline(Protocol):
    """Protocol for the agent pipeline to be evaluated."""

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        """Retrieve relevant documents for the query."""
        ...

    def analyze(self, query: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze context and produce an answer."""
        ...


@dataclass
class EvalQuestion:
    """A single evaluation question with expected answer."""

    id: str
    question: str
    expected_answer: str
    expected_relevant_docs: list[str] = field(default_factory=list)
    category: str = "general"


@dataclass
class EvalResult:
    """Result of evaluating a single question."""

    question_id: str
    question: str
    retrieved_docs: list[str]
    retrieved_doc_ids: list[str]
    answer: str
    expected_answer: str
    retrieval_precision: float
    context_relevance: float
    answer_accuracy: float
    latency_ms: float
    passed: bool


class Evaluator:
    """Evaluates agent pipeline performance against a question set."""

    def __init__(
        self,
        pipeline: AgentPipeline,
        questions_path: str | Path = "questions.json",
        output_path: str | Path = "evaluation_report.html",
        threshold: float = 0.6,
    ):
        self.pipeline = pipeline
        self.questions_path = Path(questions_path)
        self.output_path = Path(output_path)
        self.threshold = threshold
        self.results: list[EvalResult] = []

    def load_questions(self) -> list[EvalQuestion]:
        """Load evaluation questions from JSON file."""
        if not self.questions_path.exists():
            raise FileNotFoundError(f"Questions file not found: {self.questions_path}")

        with open(self.questions_path) as f:
            data = json.load(f)

        return [
            EvalQuestion(
                id=q["id"],
                question=q["question"],
                expected_answer=q["expected_answer"],
                expected_relevant_docs=q.get("expected_relevant_docs", []),
                category=q.get("category", "general"),
            )
            for q in data["questions"]
        ]

    def _compute_retrieval_precision(
        self, retrieved_docs: list[str], expected_docs: list[str]
    ) -> float:
        """Compute precision of retrieved documents against expected."""
        if not expected_docs:
            return 1.0
        if not retrieved_docs:
            return 0.0

        retrieved_set = set(retrieved_docs)
        expected_set = set(expected_docs)
        relevant = retrieved_set & expected_set
        return len(relevant) / len(retrieved_set) if retrieved_set else 0.0

    def _compute_context_relevance(
        self, context: list[dict[str, Any]], question: str
    ) -> float:
        """Compute relevance of retrieved context to the question."""
        if not context:
            return 0.0

        question_words = set(question.lower().split())
        relevance_scores = []

        for doc in context:
            doc_text = doc.get("content", "").lower()
            doc_words = set(doc_text.split())
            overlap = len(question_words & doc_words)
            relevance_scores.append(overlap / max(len(question_words), 1))

        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    def _compute_answer_accuracy(self, answer: str, expected: str) -> float:
        """Compute accuracy of generated answer against expected."""
        if not expected:
            return 1.0
        if not answer:
            return 0.0

        answer_words = set(answer.lower().split())
        expected_words = set(expected.lower().split())
        intersection = answer_words & expected_words
        return len(intersection) / len(expected_words) if expected_words else 0.0

    def evaluate_question(self, eval_q: EvalQuestion) -> EvalResult:
        """Evaluate a single question through the pipeline."""
        start_time = time.perf_counter()

        retrieved = self.pipeline.retrieve(eval_q.question)
        context = [doc for doc in retrieved if doc.get("content")]
        doc_ids = [doc.get("id", "") for doc in context]

        analysis = self.pipeline.analyze(eval_q.question, context)
        answer = analysis.get("answer", "")

        latency_ms = (time.perf_counter() - start_time) * 1000

        retrieval_precision = self._compute_retrieval_precision(
            doc_ids, eval_q.expected_relevant_docs
        )
        context_relevance = self._compute_context_relevance(
            context, eval_q.question
        )
        answer_accuracy = self._compute_answer_accuracy(answer, eval_q.expected_answer)

        overall_score = (
            retrieval_precision * 0.3
            + context_relevance * 0.3
            + answer_accuracy * 0.4
        )
        passed = overall_score >= self.threshold

        return EvalResult(
            question_id=eval_q.id,
            question=eval_q.question,
            retrieved_docs=[doc.get("content", "")[:100] for doc in context],
            retrieved_doc_ids=doc_ids,
            answer=answer,
            expected_answer=eval_q.expected_answer,
            retrieval_precision=retrieval_precision,
            context_relevance=context_relevance,
            answer_accuracy=answer_accuracy,
            latency_ms=latency_ms,
            passed=passed,
        )

    def run(self) -> list[EvalResult]:
        """Run evaluation on all questions."""
        questions = self.load_questions()
        self.results = []

        for q in questions:
            result = self.evaluate_question(q)
            self.results.append(result)

        return self.results

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of evaluation results."""
        if not self.results:
            return {"total": 0, "passed": 0, "failed": 0}

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        avg_latency = sum(r.latency_ms for r in self.results) / total
        avg_precision = sum(r.retrieval_precision for r in self.results) / total
        avg_relevance = sum(r.context_relevance for r in self.results) / total
        avg_accuracy = sum(r.answer_accuracy for r in self.results) / total

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / total * 100):.1f}%",
            "avg_latency_ms": f"{avg_latency:.1f}",
            "avg_retrieval_precision": f"{avg_precision:.3f}",
            "avg_context_relevance": f"{avg_relevance:.3f}",
            "avg_answer_accuracy": f"{avg_accuracy:.3f}",
        }

    def generate_report(self) -> str:
        """Generate HTML evaluation report."""
        summary = self.get_summary()
        rows = ""
        for r in self.results:
            status_class = "pass" if r.passed else "fail"
            rows += f"""
            <tr class="{status_class}">
                <td>{r.question_id}</td>
                <td>{r.question}</td>
                <td>{', '.join(r.retrieved_doc_ids[:3])}</td>
                <td>{r.answer[:100]}...</td>
                <td>{r.retrieval_precision:.3f}</td>
                <td>{r.context_relevance:.3f}</td>
                <td>{r.answer_accuracy:.3f}</td>
                <td>{r.latency_ms:.1f}ms</td>
                <td class="status {status_class}">{"PASS" if r.passed else "FAIL"}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AdOps Copilot Evaluation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #1a1a2e; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #666; margin-bottom: 2rem; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .summary-card {{ background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .summary-card h3 {{ color: #666; font-size: 0.875rem; text-transform: uppercase; margin-bottom: 0.5rem; }}
        .summary-card .value {{ font-size: 2rem; font-weight: bold; color: #1a1a2e; }}
        .summary-card .value.green {{ color: #10b981; }}
        .summary-card .value.red {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background: #1a1a2e; color: white; padding: 1rem; text-align: left; font-weight: 500; }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #eee; }}
        tr:last-child td {{ border-bottom: none; }}
        tr.pass td {{ background: rgba(16, 185, 129, 0.05); }}
        tr.fail td {{ background: rgba(239, 68, 68, 0.05); }}
        .status {{ font-weight: bold; }}
        .status.pass {{ color: #10b981; }}
        .status.fail {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AdOps Copilot Evaluation Report</h1>
        <p class="subtitle">Generated {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="summary-card">
                <h3>Total Questions</h3>
                <div class="value">{summary['total']}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value green">{summary['passed']}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value red">{summary['failed']}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="value">{summary['pass_rate']}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Latency</h3>
                <div class="value">{summary['avg_latency_ms']}ms</div>
            </div>
            <div class="summary-card">
                <h3>Avg Precision</h3>
                <div class="value">{summary['avg_retrieval_precision']}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Relevance</h3>
                <div class="value">{summary['avg_context_relevance']}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Accuracy</h3>
                <div class="value">{summary['avg_answer_accuracy']}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Question</th>
                    <th>Retrieved Docs</th>
                    <th>Answer</th>
                    <th>Precision</th>
                    <th>Relevance</th>
                    <th>Accuracy</th>
                    <th>Latency</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        self.output_path.write_text(html)
        return str(self.output_path)

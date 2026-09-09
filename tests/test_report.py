"""Cost/latency rendering appears only for real-model runs."""

from __future__ import annotations

from plancomply.models import (
    DocumentReport,
    ReliabilityReport,
    RuleResult,
    Status,
    Verdict,
)
from plancomply.report import render_document_report, render_reliability_report


def _result(rule_id: str, tokens: int) -> RuleResult:
    return RuleResult(
        verdict=Verdict(rule_id=rule_id, status=Status.COMPLIANT),
        latency_ms=800.0,
        prompt_tokens=tokens,
        completion_tokens=tokens // 4,
    )


def test_document_report_shows_cost_for_llm_run() -> None:
    report = DocumentReport(
        doc_id="doc-1",
        project="P",
        applier="llm:gpt-4o",
        results=[_result("ACC-CIRC-140", 400)],
    )
    text = render_document_report(report)
    assert "Coût estimé: $" in text
    assert "Tokens: 500" in text


def test_document_report_hides_cost_offline() -> None:
    report = DocumentReport(
        doc_id="doc-1",
        project="P",
        applier="heuristic",
        results=[
            RuleResult(verdict=Verdict(rule_id="ACC-CIRC-140", status=Status.COMPLIANT))
        ],
    )
    text = render_document_report(report)
    assert "Coût estimé" not in text
    assert "Tokens" not in text


def test_reliability_report_shows_cost_and_latency_for_llm() -> None:
    rel = ReliabilityReport(
        applier_name="llm:gpt-4o",
        total=25,
        agree=24,
        false_negatives=1,
        false_positives=0,
        true_violations=5,
        prompt_tokens=10_000,
        completion_tokens=2_000,
        total_latency_ms=20_000.0,
    )
    text = render_reliability_report(rel)
    assert "Coût:" in text
    assert "/doc" in text
    assert "Latence:" in text

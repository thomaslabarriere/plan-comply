"""Orchestration: apply the rule set to documents, capturing latency + usage."""

from __future__ import annotations

import time

from .appliers import Applier, Usage
from .models import DocumentReport, PlanDocument, Rule, RuleResult


def run_document(applier: Applier, doc: PlanDocument, rules: list[Rule]) -> DocumentReport:
    """Apply every rule to one document, timing each call.

    An applier that raises on a single rule does not sink the document: the
    failure is isolated into an error verdict for that rule (never confirming
    compliance it did not establish).
    """
    from .models import Status, Verdict

    results: list[RuleResult] = []
    for rule in rules:
        start = time.perf_counter()
        usage: Usage | None
        try:
            verdict, usage = applier.apply(doc, rule)
        except Exception as exc:  # noqa: BLE001 - isolate per-rule failures
            verdict = Verdict(
                rule_id=rule.rule_id,
                status=Status.NOT_APPLICABLE,
                explanation=f"[erreur automation] {exc}",
            )
            usage = None
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(
            RuleResult(
                verdict=verdict,
                latency_ms=latency_ms,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )
        )
    return DocumentReport(doc_id=doc.doc_id, project=doc.project, results=results)


def run_corpus(
    applier: Applier, docs: list[PlanDocument], rules: list[Rule]
) -> list[DocumentReport]:
    return [run_document(applier, doc, rules) for doc in docs]

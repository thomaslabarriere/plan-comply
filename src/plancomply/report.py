"""Render the shippable artifacts: the per-document compliance report and the
reliability report."""

from __future__ import annotations

from .models import DocumentReport, ReliabilityReport, Status
from .rules import get_rule

_MARK = {
    Status.COMPLIANT: "OK ",
    Status.VIOLATION: "!! ",
    Status.NOT_APPLICABLE: "-- ",
}


def render_document_report(report: DocumentReport) -> str:
    lines: list[str] = []
    rule_bar = "─" * 64
    lines.append(rule_bar)
    lines.append(f"Rapport de conformité — {report.project} [{report.doc_id}]")
    lines.append(rule_bar)

    violations = report.violations
    lines.append(
        f"Violations: {len(violations)} / {len(report.results)} règles vérifiées"
    )
    lines.append("")

    for result in report.results:
        v = result.verdict
        rule = get_rule(v.rule_id)
        lines.append(f"{_MARK[v.status]}{v.rule_id} — {rule.title}")
        if v.evidence:
            lines.append(f"      preuve: {v.evidence}")
        if v.explanation:
            lines.append(f"      {v.explanation}")

    # Resolution-time framing: what this run would have cost a human vs. the
    # machine. Manual minutes cover only the rules that were actually checked.
    manual_minutes = sum(get_rule(r.verdict.rule_id).manual_minutes for r in report.results)
    auto_seconds = sum(r.latency_ms for r in report.results) / 1000
    lines.append("")
    lines.append("Temps de résolution")
    lines.append(f"  Manuel (estimé): {manual_minutes:.0f} min")
    if auto_seconds > 0:
        lines.append(f"  Automatisé: {auto_seconds:.2f} s")
    tokens = sum(r.prompt_tokens + r.completion_tokens for r in report.results)
    if tokens > 0:
        lines.append(f"  Tokens: {tokens}")
    lines.append(rule_bar)
    return "\n".join(lines)


def render_reliability_report(rel: ReliabilityReport) -> str:
    lines: list[str] = []
    rule_bar = "─" * 64
    lines.append(rule_bar)
    lines.append(f"Fiabilité de l'automatisation — {rel.applier_name}")
    lines.append(rule_bar)
    lines.append(
        f"Recall sur violations: {rel.violation_recall * 100:.0f}% "
        f"({rel.true_violations - rel.false_negatives}/{rel.true_violations} détectées)"
    )
    lines.append(f"Violations manquées (faux négatifs): {rel.false_negatives}")
    lines.append(f"Fausses alertes (faux positifs): {rel.false_positives}")
    lines.append(
        f"Accord global: {rel.agreement_rate * 100:.0f}% ({rel.agree}/{rel.total})"
    )
    lines.append(rule_bar)
    return "\n".join(lines)

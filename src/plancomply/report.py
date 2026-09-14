"""Render the shippable artifacts: the per-document compliance report and the
reliability report."""

from __future__ import annotations

from .models import DocumentReport, ReliabilityReport, Status
from .pricing import estimate_usd, model_from_applier
from .rules import RULES, get_rule

_MARK = {
    Status.COMPLIANT: "OK ",
    Status.VIOLATION: "!! ",
    Status.NOT_APPLICABLE: "-- ",
}


def render_document_report(report: DocumentReport) -> str:
    lines: list[str] = []
    rule_bar = "─" * 64
    lines.append(rule_bar)
    lines.append(f"Rapport de conformité: {report.project} [{report.doc_id}]")
    lines.append(rule_bar)

    violations = report.violations
    lines.append(
        f"Violations: {len(violations)} / {len(report.results)} règles vérifiées"
    )
    lines.append("")

    for result in report.results:
        v = result.verdict
        rule = get_rule(v.rule_id)
        lines.append(f"{_MARK[v.status]}{v.rule_id}: {rule.title}")
        if v.evidence:
            lines.append(f"      preuve: {v.evidence}")
        if v.explanation:
            lines.append(f"      {v.explanation}")

    # Resolution-time framing: what this run would have cost a human vs. the
    # machine. Manual minutes cover only the rules that actually APPLIED -- a
    # not-applicable rule (e.g. a fire rule on a non-ERP dwelling) costs the
    # expert no resolution time, so counting it would overstate the ROI.
    manual_minutes = sum(
        get_rule(r.verdict.rule_id).manual_minutes
        for r in report.results
        if r.verdict.status is not Status.NOT_APPLICABLE
    )
    auto_seconds = sum(r.latency_ms for r in report.results) / 1000
    lines.append("")
    lines.append("Temps de résolution")
    lines.append(f"  Manuel (estimé): {manual_minutes:.0f} min")
    if auto_seconds > 0:
        lines.append(f"  Automatisé: {auto_seconds:.2f} s")
    tokens = report.prompt_tokens + report.completion_tokens
    if tokens > 0:
        lines.append(f"  Tokens: {tokens}")
        usd = estimate_usd(
            model_from_applier(report.applier),
            report.prompt_tokens,
            report.completion_tokens,
        )
        if usd is not None:
            lines.append(f"  Coût estimé: ${usd:.4f} (prix catalogue indicatif)")
    lines.append(rule_bar)
    return "\n".join(lines)


def render_reliability_report(rel: ReliabilityReport) -> str:
    lines: list[str] = []
    rule_bar = "─" * 64
    lines.append(rule_bar)
    lines.append(f"Fiabilité de l'automatisation: {rel.applier_name}")
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
    tokens = rel.prompt_tokens + rel.completion_tokens
    if tokens > 0:
        usd = estimate_usd(
            model_from_applier(rel.applier_name), rel.prompt_tokens, rel.completion_tokens
        )
        # Per-doc cost assumes the gold set is a full doc×rule cross-product
        # (as build_gold_set produces); guard so a future sampled gold set
        # degrades to a total-only figure rather than a misleading per-doc one.
        docs = rel.total // len(RULES) if RULES and rel.total % len(RULES) == 0 else 0
        cost_line = f"Coût: {tokens} tokens"
        if usd is not None:
            per_doc = f", ${usd / docs:.4f}/doc" if docs else ""
            cost_line += f", ${usd:.4f} sur {rel.total} contrôles{per_doc}"
        lines.append(cost_line)
        lines.append(
            f"Latence: {rel.total_latency_ms / rel.total:.0f} ms/contrôle "
            f"({rel.total_latency_ms / 1000:.2f} s au total)"
        )
    lines.append(rule_bar)
    return "\n".join(lines)


def render_reliability_comparison(reports: list[ReliabilityReport]) -> str:
    """Side-by-side recall of several appliers (baseline vs LLM)."""
    rule_bar = "═" * 64
    lines = [rule_bar, "Comparaison de fiabilité (recall sur violations)", "─" * 64]
    name_width = max((len(r.applier_name) for r in reports), default=10)
    header = f"  {'applier'.ljust(name_width)}   recall   manquées   fausses alertes"
    lines.append(header)
    for r in reports:
        lines.append(
            f"  {r.applier_name.ljust(name_width)}   "
            f"{r.violation_recall * 100:>4.0f}%   "
            f"{r.false_negatives:>8}   {r.false_positives:>14}"
        )
    lines.append(rule_bar)
    return "\n".join(lines)

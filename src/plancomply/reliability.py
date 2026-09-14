"""The reliability instrument: does the automation actually catch violations?

This is the differentiator. An automation that ships into a compliance report
is only trustworthy if you can state how often it MISSES a real violation (a
false negative) -- the failure mode that destroys client trust. This module
runs the automation over the labelled gold set and reports violation recall,
false negatives, and false positives.
"""

from __future__ import annotations

import time

from .appliers import Applier, Usage
from .documents import get_document
from .models import GoldItem, ReliabilityReport, Status, Verdict
from .rules import get_rule


def evaluate_reliability(applier: Applier, gold: list[GoldItem]) -> ReliabilityReport:
    total = len(gold)
    agree = 0
    false_negatives = 0
    false_positives = 0
    true_violations = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_latency_ms = 0.0

    for item in gold:
        doc = get_document(item.doc_id)
        rule = get_rule(item.rule_id)
        start = time.perf_counter()
        try:
            verdict, usage = applier.apply(doc, rule)
        except Exception as exc:  # noqa: BLE001 - isolate + attribute per-rule failures
            # A single raising rule must NOT sink the whole reliability run. The
            # failure is isolated into an undecided verdict (never "compliant"),
            # so wherever a real violation existed it is counted as an honest
            # false negative below rather than crashing the measurement.
            verdict = Verdict(
                rule_id=rule.rule_id,
                status=Status.NOT_APPLICABLE,
                explanation=f"[erreur automation] {exc}",
            )
            usage = Usage()
        total_latency_ms += (time.perf_counter() - start) * 1000
        prompt_tokens += usage.prompt_tokens
        completion_tokens += usage.completion_tokens
        got = verdict.status
        expected = item.expected

        if expected is Status.VIOLATION:
            true_violations += 1
        if got is expected:
            agree += 1
            continue
        # Disagreement: classify by consequence.
        if expected is Status.VIOLATION and got is not Status.VIOLATION:
            false_negatives += 1  # a MISSED violation
        elif expected is not Status.VIOLATION and got is Status.VIOLATION:
            false_positives += 1  # a false alarm

    return ReliabilityReport(
        applier_name=applier.name,
        total=total,
        agree=agree,
        false_negatives=false_negatives,
        false_positives=false_positives,
        true_violations=true_violations,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_latency_ms=total_latency_ms,
    )


def compare_reliability(
    appliers: list[Applier], gold: list[GoldItem]
) -> list[ReliabilityReport]:
    """Grade several appliers against the same gold set (baseline vs LLM).

    This answers the question a team actually asks before shipping: does the
    LLM automation close the false-negative gap the cheap baseline leaves open?
    """
    return [evaluate_reliability(applier, gold) for applier in appliers]

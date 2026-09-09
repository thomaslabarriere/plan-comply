"""The reliability instrument: does the automation actually catch violations?

This is the differentiator. An automation that ships into a compliance report
is only trustworthy if you can state how often it MISSES a real violation (a
false negative) -- the failure mode that destroys client trust. This module
runs the automation over the labelled gold set and reports violation recall,
false negatives, and false positives.
"""

from __future__ import annotations

from .appliers import Applier
from .documents import get_document
from .models import GoldItem, ReliabilityReport, Status
from .rules import get_rule


def evaluate_reliability(applier: Applier, gold: list[GoldItem]) -> ReliabilityReport:
    total = len(gold)
    agree = 0
    false_negatives = 0
    false_positives = 0
    true_violations = 0

    for item in gold:
        doc = get_document(item.doc_id)
        rule = get_rule(item.rule_id)
        verdict, _ = applier.apply(doc, rule)
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
    )

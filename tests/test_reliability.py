"""Mutation proof for the reliability instrument.

If the instrument that measures the automation is itself wrong, the whole
deliverable is worthless -- so a blind automation MUST be caught (recall 0), a
perfect one MUST NOT be flagged (recall 1), and the offline baseline's known
false-negative gap MUST be reported exactly.
"""

from __future__ import annotations

from plancomply.appliers import BlindApplier, GoldApplier, HeuristicApplier
from plancomply.documents import get_document
from plancomply.goldset import build_gold_set
from plancomply.reliability import compare_reliability, evaluate_reliability
from plancomply.report import render_reliability_comparison
from plancomply.rules import RULES
from plancomply.runner import run_document


def test_blind_automation_misses_every_violation() -> None:
    rel = evaluate_reliability(BlindApplier(), build_gold_set())
    assert rel.true_violations == 5
    assert rel.false_negatives == 5
    assert rel.violation_recall == 0.0


def test_gold_automation_is_not_falsely_flagged() -> None:
    gold = build_gold_set()
    rel = evaluate_reliability(GoldApplier(gold), gold)
    assert rel.false_negatives == 0
    assert rel.false_positives == 0
    assert rel.violation_recall == 1.0
    assert rel.agreement_rate == 1.0


def test_heuristic_baseline_gap_is_reported_exactly() -> None:
    # The keyword baseline cannot handle negation: doc-4 says an ERP mentions
    # NO alarm ("aucun ... d'alarme"), but the word "alarme" is present, so the
    # baseline wrongly passes it. The instrument must surface that ONE miss.
    rel = evaluate_reliability(HeuristicApplier(), build_gold_set())
    assert rel.false_negatives == 1
    assert rel.false_positives == 0
    assert rel.violation_recall == 0.8  # 4 of 5 true violations caught


def test_compare_ranks_appliers_by_recall() -> None:
    gold = build_gold_set()
    reports = compare_reliability([BlindApplier(), GoldApplier(gold)], gold)
    assert [r.applier_name for r in reports] == ["blind", "gold"]
    assert reports[0].violation_recall == 0.0
    assert reports[1].violation_recall == 1.0
    rendered = render_reliability_comparison(reports)
    assert "blind" in rendered and "gold" in rendered


def test_run_document_isolates_a_raising_applier() -> None:
    class Boom:
        name = "boom"

        def apply(self, doc, rule):  # type: ignore[no-untyped-def]
            raise RuntimeError("kaboom")

    report = run_document(Boom(), get_document("doc-1"), RULES)
    assert len(report.results) == len(RULES)
    assert all("erreur automation" in r.verdict.explanation for r in report.results)


def test_reliability_isolates_a_raising_rule() -> None:
    # A single raising rule must NOT crash the reliability run: the failure is
    # caught and attributed. Here the applier raises ONLY on FIRE-ALARM-ERP.
    from plancomply.appliers import Usage
    from plancomply.models import Verdict

    class RaisesOnAlarm:
        name = "raises-on-alarm"

        def apply(self, doc, rule):  # type: ignore[no-untyped-def]
            if rule.rule_id == "FIRE-ALARM-ERP":
                raise RuntimeError("boom on alarm")
            # Otherwise behave like a perfect oracle so we can isolate the effect.
            status = {
                g.rule_id: g.expected for g in build_gold_set() if g.doc_id == doc.doc_id
            }[rule.rule_id]
            return Verdict(rule_id=rule.rule_id, status=status), Usage()

    gold = build_gold_set()
    rel = evaluate_reliability(RaisesOnAlarm(), gold)
    # The run COMPLETED (not fatal) and graded all 25 controls.
    assert rel.total == len(gold) == 25
    # FIRE-ALARM-ERP has one true violation (doc-4); the raise is attributed as
    # an undecided verdict, i.e. an honest missed violation, never "compliant".
    assert rel.false_negatives == 1
    assert rel.false_positives == 0

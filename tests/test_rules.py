"""The rule base, parser, and gold set are internally consistent."""

from __future__ import annotations

from plancomply.documents import get_document, load_corpus, parse_plan_sheet
from plancomply.goldset import build_gold_set
from plancomply.models import Status
from plancomply.rules import REFERENCE_CHECKS, RULES, RuleKind


def test_parser_extracts_elements_and_narrative() -> None:
    doc = get_document("doc-2")
    assert doc.project == "Résidence Les Tilleuls"
    corridor = next(e for e in doc.elements if e.kind == "corridor")
    assert corridor.attributes["width_m"] == 1.20
    assert "logements" in doc.narrative.lower()


def test_parser_ignores_non_numeric_attributes() -> None:
    doc = parse_plan_sheet(
        "# ELEMENTS\ncorridor | C1 | width_m=1.5, note=tbd\n# NARRATIVE\nx"
    )
    (corridor,) = doc.elements
    assert corridor.attributes == {"width_m": 1.5}


def test_structured_reference_checks_match_documents() -> None:
    # Regression guard: the objective checks agree with the corpus as authored.
    doc2 = get_document("doc-2")
    assert REFERENCE_CHECKS["ACC-CIRC-140"](doc2) is Status.VIOLATION  # 1.20 < 1.40
    doc3 = get_document("doc-3")
    assert REFERENCE_CHECKS["ACC-RAMP-05"](doc3) is Status.VIOLATION  # 8.0 > 5
    doc4 = get_document("doc-4")
    assert REFERENCE_CHECKS["ACC-DOOR-090"](doc4) is Status.VIOLATION  # 0.82 < 0.90
    doc1 = get_document("doc-1")
    assert REFERENCE_CHECKS["ACC-CIRC-140"](doc1) is Status.COMPLIANT  # 1.60


def test_gold_set_shape() -> None:
    gold = build_gold_set()
    assert len(gold) == len(load_corpus()) * len(RULES) == 25
    true_violations = [g for g in gold if g.expected is Status.VIOLATION]
    assert len(true_violations) == 5  # one per rule, spread across documents


def test_every_rule_is_covered_by_a_check_or_judgment() -> None:
    for rule in RULES:
        if rule.kind is RuleKind.STRUCTURED:
            assert rule.rule_id in REFERENCE_CHECKS


def test_hand_labels_stay_defensible_against_the_corpus() -> None:
    # The gold set is authored INDEPENDENTLY of the applier (no tautology). This
    # guard is not the measurement: it re-derives the objective structured truth
    # from the measured fields and asserts the HAND-WRITTEN gold labels still
    # match the corpus, so an edit to a document that silently invalidates a
    # label fails loudly instead of skewing the reported agreement.
    gold = {(g.doc_id, g.rule_id): g.expected for g in build_gold_set()}
    for doc in load_corpus():
        for rule in RULES:
            if rule.kind is RuleKind.STRUCTURED:
                objective = REFERENCE_CHECKS[rule.rule_id](doc)
                assert gold[(doc.doc_id, rule.rule_id)] is objective

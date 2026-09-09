"""The labelled gold set: the ground truth the automation is measured against.

STRUCTURED rules are labelled objectively by their reference check over the
document's measured fields (so the labels can never silently drift from the
corpus). JUDGMENT rules are labelled by hand here, because they turn on reading
the narrative -- this is the honest boundary between what a field lookup can
decide and what needs an expert (or a well-calibrated LLM).
"""

from __future__ import annotations

from .documents import load_corpus
from .models import GoldItem, RuleKind, Status
from .rules import REFERENCE_CHECKS, RULES

# Hand-authored ground truth for the JUDGMENT rules, keyed (doc_id, rule_id).
# Each label is defensible from the narrative text in documents.py.
_JUDGMENT_LABELS: dict[tuple[str, str], Status] = {
    # FIRE-EVAC-ROUTE (scoped to ERP)
    ("doc-1", "FIRE-EVAC-ROUTE"): Status.COMPLIANT,       # ERP, route described
    ("doc-2", "FIRE-EVAC-ROUTE"): Status.NOT_APPLICABLE,  # non-ERP dwelling
    ("doc-3", "FIRE-EVAC-ROUTE"): Status.VIOLATION,       # ERP, no route described
    ("doc-4", "FIRE-EVAC-ROUTE"): Status.COMPLIANT,       # ERP, two exits described
    ("doc-5", "FIRE-EVAC-ROUTE"): Status.NOT_APPLICABLE,  # non-ERP house
    # FIRE-ALARM-ERP
    ("doc-1", "FIRE-ALARM-ERP"): Status.COMPLIANT,        # ERP, alarm 2b mentioned
    ("doc-2", "FIRE-ALARM-ERP"): Status.NOT_APPLICABLE,   # non-ERP dwelling
    ("doc-3", "FIRE-ALARM-ERP"): Status.COMPLIANT,        # ERP, generalised alarm
    ("doc-4", "FIRE-ALARM-ERP"): Status.VIOLATION,        # ERP, no alarm mentioned
    ("doc-5", "FIRE-ALARM-ERP"): Status.NOT_APPLICABLE,   # non-ERP house
}


def build_gold_set() -> list[GoldItem]:
    """Every (document, rule) pair with its ground-truth status."""
    corpus = load_corpus()
    items: list[GoldItem] = []
    for doc in corpus:
        for rule in RULES:
            if rule.kind is RuleKind.STRUCTURED:
                expected = REFERENCE_CHECKS[rule.rule_id](doc)
            else:
                expected = _JUDGMENT_LABELS[(doc.doc_id, rule.rule_id)]
            items.append(
                GoldItem(doc_id=doc.doc_id, rule_id=rule.rule_id, expected=expected)
            )
    return items

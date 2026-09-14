"""The labelled gold set: the ground truth the automation is measured against.

This gold set is INDEPENDENT ground truth. Every label below is hand-authored
by reading each synthetic document once and writing down the answer a compliance
expert would give -- it is NOT computed from the same `REFERENCE_CHECKS` the
`HeuristicApplier` uses. That decoupling matters: if the gold were built from
the very code under test, the reported agreement would partly be the code
grading itself (a tautology). Here the applier and the gold are two independent
opinions, so the agreement number means what it claims to.

Each structured label is defensible from the measured field written in
`documents.py` (e.g. doc-2's corridor is 1.20 m < 1.40 m -> VIOLATION); each
judgment label is defensible from the narrative text. The regression test
`test_gold_labels_match_the_authored_corpus` pins these against the corpus so a
future edit to a document that would invalidate a label fails loudly.
"""

from __future__ import annotations

from .models import GoldItem, Status

# Independent, hand-authored ground truth for EVERY (doc_id, rule_id) pair.
# Written by reading documents.py directly -- never derived from REFERENCE_CHECKS.
_GOLD_LABELS: dict[tuple[str, str], Status] = {
    # --- ACC-CIRC-140: corridor libre >= 1,40 m -----------------------------
    ("doc-1", "ACC-CIRC-140"): Status.COMPLIANT,       # couloir 1,60 m
    ("doc-2", "ACC-CIRC-140"): Status.VIOLATION,       # couloir 1,20 m < 1,40 m
    ("doc-3", "ACC-CIRC-140"): Status.COMPLIANT,       # galerie 2,00 m
    ("doc-4", "ACC-CIRC-140"): Status.COMPLIANT,       # allée 1,80 m
    ("doc-5", "ACC-CIRC-140"): Status.COMPLIANT,       # dégagement 1,45 m
    # --- ACC-DOOR-090: passage utile de porte >= 0,90 m ---------------------
    ("doc-1", "ACC-DOOR-090"): Status.COMPLIANT,       # porte 0,93 m
    ("doc-2", "ACC-DOOR-090"): Status.COMPLIANT,       # porte 0,90 m (pile la limite)
    ("doc-3", "ACC-DOOR-090"): Status.COMPLIANT,       # entrée 1,20 m
    ("doc-4", "ACC-DOOR-090"): Status.VIOLATION,       # sas 0,82 m < 0,90 m
    ("doc-5", "ACC-DOOR-090"): Status.COMPLIANT,       # porte 0,95 m
    # --- ACC-RAMP-05: pente de rampe <= 5% ----------------------------------
    ("doc-1", "ACC-RAMP-05"): Status.COMPLIANT,        # rampe 4,0%
    ("doc-2", "ACC-RAMP-05"): Status.COMPLIANT,        # rampe 5,0% (pile la limite)
    ("doc-3", "ACC-RAMP-05"): Status.VIOLATION,        # rampe 8,0% > 5%
    ("doc-4", "ACC-RAMP-05"): Status.COMPLIANT,        # rampe 3,5%
    ("doc-5", "ACC-RAMP-05"): Status.COMPLIANT,        # rampe 4,5%
    # --- FIRE-EVAC-ROUTE (scoped to ERP) ------------------------------------
    ("doc-1", "FIRE-EVAC-ROUTE"): Status.COMPLIANT,       # ERP, itinéraire décrit
    ("doc-2", "FIRE-EVAC-ROUTE"): Status.NOT_APPLICABLE,  # logements, non ERP
    ("doc-3", "FIRE-EVAC-ROUTE"): Status.VIOLATION,       # ERP, aucun itinéraire décrit
    ("doc-4", "FIRE-EVAC-ROUTE"): Status.COMPLIANT,       # ERP, deux sorties de secours
    ("doc-5", "FIRE-EVAC-ROUTE"): Status.NOT_APPLICABLE,  # maison, non ERP
    # --- FIRE-ALARM-ERP -----------------------------------------------------
    ("doc-1", "FIRE-ALARM-ERP"): Status.COMPLIANT,        # ERP, alarme sonore 2b
    ("doc-2", "FIRE-ALARM-ERP"): Status.NOT_APPLICABLE,   # logements, non ERP
    ("doc-3", "FIRE-ALARM-ERP"): Status.COMPLIANT,        # ERP, alarme généralisée
    ("doc-4", "FIRE-ALARM-ERP"): Status.VIOLATION,        # ERP, AUCUN dispositif d'alarme
    ("doc-5", "FIRE-ALARM-ERP"): Status.NOT_APPLICABLE,   # maison, non ERP
}


def build_gold_set() -> list[GoldItem]:
    """Every (document, rule) pair with its hand-authored ground-truth status."""
    return [
        GoldItem(doc_id=doc_id, rule_id=rule_id, expected=expected)
        for (doc_id, rule_id), expected in _GOLD_LABELS.items()
    ]

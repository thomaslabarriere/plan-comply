"""The compliance rule set (synthetic, simplified, illustrative).

Each rule carries the plain-language statement a compliance expert would apply.
STRUCTURED rules also have a deterministic reference check over measured fields
(used to build the gold set and as the objective ground truth); JUDGMENT rules
are labelled by hand in goldset.py because they turn on reading the narrative.

These thresholds are LOOSELY inspired by public accessibility/fire concepts and
are NOT the actual regulation. Swap in the real rule base to make it authoritative.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import PlanDocument, Rule, RuleKind, Status

RULES: list[Rule] = [
    Rule(
        rule_id="ACC-CIRC-140",
        title="Largeur de circulation",
        statement=(
            "Toute circulation horizontale commune doit offrir une largeur libre "
            "d'au moins 1,40 m. Vérifier chaque élément 'corridor' : sa largeur "
            "(width_m) doit être >= 1.40. En-dessous, c'est une violation."
        ),
        kind=RuleKind.STRUCTURED,
        manual_minutes=2.0,
    ),
    Rule(
        rule_id="ACC-DOOR-090",
        title="Passage utile de porte",
        statement=(
            "Une porte sur un cheminement accessible doit offrir un passage utile "
            "d'au moins 0,90 m. Vérifier chaque 'door' : clear_width_m doit être "
            ">= 0.90. En-dessous, violation."
        ),
        kind=RuleKind.STRUCTURED,
        manual_minutes=2.0,
    ),
    Rule(
        rule_id="ACC-RAMP-05",
        title="Pente de rampe",
        statement=(
            "Une rampe accessible ne doit pas dépasser 5% de pente. Vérifier chaque "
            "'ramp' : slope_pct doit être <= 5. Au-delà, violation."
        ),
        kind=RuleKind.STRUCTURED,
        manual_minutes=2.0,
    ),
    Rule(
        rule_id="FIRE-EVAC-ROUTE",
        title="Itinéraire d'évacuation",
        statement=(
            "Un établissement recevant du public (ERP) doit décrire un itinéraire "
            "d'évacuation menant sans ambiguïté à une sortie de secours identifiée. "
            "Si le document décrit un ERP mais aucune narration d'itinéraire "
            "d'évacuation ni de sortie de secours, c'est une violation. Si le local "
            "n'est pas un ERP, la règle est non applicable."
        ),
        kind=RuleKind.JUDGMENT,
        manual_minutes=6.0,
    ),
    Rule(
        rule_id="FIRE-ALARM-ERP",
        title="Alarme incendie en ERP",
        statement=(
            "Un local recevant du public (ERP) doit mentionner un dispositif "
            "d'alarme incendie. Si le document décrit un ERP mais ne mentionne "
            "aucun dispositif d'alarme, c'est une violation. Si le local n'est "
            "pas un ERP, la règle est non applicable."
        ),
        kind=RuleKind.JUDGMENT,
        manual_minutes=5.0,
    ),
]


def get_rule(rule_id: str) -> Rule:
    for rule in RULES:
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(f"unknown rule {rule_id!r}")


# --- Deterministic reference checks for STRUCTURED rules ---------------------
# These encode the objective truth for structured rules over measured fields.
# They are the ground-truth oracle (not the automation under test): the LLM
# applier must REDISCOVER these verdicts from the rule statement + document.

def _check_min_attr(
    doc: PlanDocument, element_kind: str, attr: str, minimum: float
) -> Status:
    relevant = [e for e in doc.elements if e.kind == element_kind]
    if not relevant:
        return Status.NOT_APPLICABLE
    for element in relevant:
        value = element.attributes.get(attr)
        if value is not None and value < minimum:
            return Status.VIOLATION
    return Status.COMPLIANT


def _check_max_attr(
    doc: PlanDocument, element_kind: str, attr: str, maximum: float
) -> Status:
    relevant = [e for e in doc.elements if e.kind == element_kind]
    if not relevant:
        return Status.NOT_APPLICABLE
    for element in relevant:
        value = element.attributes.get(attr)
        if value is not None and value > maximum:
            return Status.VIOLATION
    return Status.COMPLIANT


REFERENCE_CHECKS: dict[str, Callable[[PlanDocument], Status]] = {
    "ACC-CIRC-140": lambda d: _check_min_attr(d, "corridor", "width_m", 1.40),
    "ACC-DOOR-090": lambda d: _check_min_attr(d, "door", "clear_width_m", 0.90),
    "ACC-RAMP-05": lambda d: _check_max_attr(d, "ramp", "slope_pct", 5.0),
}

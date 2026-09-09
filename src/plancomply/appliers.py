"""Appliers: the automation that takes (document, rule) -> Verdict.

`LLMApplier` is the real automation -- it hands the rule statement and the
parsed document to an LLM and asks for a structured verdict. `HeuristicApplier`
is an offline, network-free baseline (reference checks for structured rules,
narrative keyword rules for judgment rules) so the whole pipeline -- including
the reliability instrument -- runs with no API key. `BlindApplier` and
`GoldApplier` are test fixtures (mutation proof + control).

Every applier returns (Verdict, Usage); the runner times the call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from .models import GoldItem, PlanDocument, Rule, RuleKind, Status, Verdict
from .rules import REFERENCE_CHECKS


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Applier(Protocol):
    name: str

    def apply(self, doc: PlanDocument, rule: Rule) -> tuple[Verdict, Usage]: ...


def render_document(doc: PlanDocument) -> str:
    """Compact, LLM-friendly rendering of a parsed plan sheet."""
    lines = [f"Projet: {doc.project}", f"Discipline: {doc.discipline}", "Éléments:"]
    if doc.elements:
        for el in doc.elements:
            attrs = ", ".join(f"{k}={v}" for k, v in sorted(el.attributes.items()))
            lines.append(f"  - {el.kind} « {el.label} » ({attrs or 'aucune mesure'})")
    else:
        lines.append("  (aucun élément mesuré)")
    lines.append(f"Narration: {doc.narrative or '(vide)'}")
    return "\n".join(lines)


# --- Real automation: LLM applier -------------------------------------------

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_TOOL = {
    "type": "function",
    "function": {
        "name": "report_verdict",
        "description": "Report whether the plan document complies with the rule.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["compliant", "violation", "not_applicable"],
                    "description": "compliant, violation, or not_applicable.",
                },
                "evidence": {
                    "type": "string",
                    "description": "The measured value or narrative quote grounding the verdict.",
                },
                "explanation": {
                    "type": "string",
                    "description": "One sentence: why this status.",
                },
            },
            "required": ["status", "explanation"],
            "additionalProperties": False,
        },
    },
}

_SYSTEM_PROMPT = (
    "Tu es un vérificateur de conformité BTP rigoureux. On te donne UNE règle et "
    "UN document de plan. Décide si le document est conforme (compliant), en "
    "violation (violation), ou si la règle ne s'applique pas (not_applicable). "
    "Fonde-toi UNIQUEMENT sur le document fourni. En cas de doute sur une "
    "violation potentielle, signale-la plutôt que de la masquer. Tu dois appeler "
    "l'outil report_verdict."
)


class LLMApplier:
    """The shippable automation. Needs OPENAI_API_KEY (or OPENROUTER_API_KEY)."""

    def __init__(
        self,
        model: str,
        provider: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        self.name = f"llm:{model}"
        self._model = model
        if base_url is None and provider == "openrouter":
            base_url = _OPENROUTER_BASE_URL
        if api_key is None:
            api_key = os.environ.get(
                "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def apply(self, doc: PlanDocument, rule: Rule) -> tuple[Verdict, Usage]:
        user = (
            f"Règle {rule.rule_id} — {rule.title}\n{rule.statement}\n\n"
            f"Document:\n{render_document(doc)}"
        )
        try:
            completion = self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                tools=[_TOOL],
                tool_choice="required",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - surface as an undecided verdict
            return self._error(rule, f"appel API échoué: {exc}")

        usage = Usage(
            prompt_tokens=getattr(completion.usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(completion.usage, "completion_tokens", 0) or 0,
        )
        message = completion.choices[0].message if completion.choices else None
        for call in getattr(message, "tool_calls", None) or []:
            if getattr(call, "type", None) != "function":
                continue
            if call.function.name != "report_verdict":
                continue
            verdict = self._parse(rule, call.function.arguments)
            if verdict is not None:
                return verdict, usage
        return self._error(rule, "aucun verdict exploitable retourné")[0], usage

    @staticmethod
    def _parse(rule: Rule, args_json: str) -> Verdict | None:
        try:
            data = json.loads(args_json)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        raw = data.get("status")
        if not isinstance(raw, str):
            return None
        try:
            status = Status(raw)
        except ValueError:
            return None
        evidence = data.get("evidence")
        return Verdict(
            rule_id=rule.rule_id,
            status=status,
            evidence=evidence if isinstance(evidence, str) else None,
            explanation=str(data.get("explanation", "")),
        )

    @staticmethod
    def _error(rule: Rule, message: str) -> tuple[Verdict, Usage]:
        # An undecided call cannot confirm compliance. It is left NOT_APPLICABLE
        # with an error note; the reliability instrument then counts it as a
        # miss wherever a real violation existed (an honest false negative).
        return (
            Verdict(
                rule_id=rule.rule_id,
                status=Status.NOT_APPLICABLE,
                explanation=f"[erreur automation] {message}",
            ),
            Usage(),
        )


# --- Offline baseline automation --------------------------------------------


def _is_erp(narrative: str) -> bool:
    text = narrative.lower()
    if "non erp" in text or "non-erp" in text:
        return False
    return "erp" in text or "recevant du public" in text


class HeuristicApplier:
    """Network-free baseline: reference checks + narrative keyword rules.

    Deliberately simple -- it is a REALISTIC imperfect automation whose recall
    is worth measuring, not an oracle. It lets the full pipeline (and the
    reliability report) run offline.
    """

    name = "heuristic"

    def apply(self, doc: PlanDocument, rule: Rule) -> tuple[Verdict, Usage]:
        if rule.kind is RuleKind.STRUCTURED:
            status = REFERENCE_CHECKS[rule.rule_id](doc)
            return (
                Verdict(rule_id=rule.rule_id, status=status, explanation="contrôle mesuré"),
                Usage(),
            )
        return self._judge(doc, rule), Usage()

    def _judge(self, doc: PlanDocument, rule: Rule) -> Verdict:
        narrative = doc.narrative.lower()
        not_erp = Verdict(
            rule_id=rule.rule_id, status=Status.NOT_APPLICABLE, explanation="non-ERP"
        )
        if rule.rule_id == "FIRE-EVAC-ROUTE":
            if not _is_erp(narrative):
                return not_erp
            has_route = "évacuation" in narrative or "sortie de secours" in narrative
            return Verdict(
                rule_id=rule.rule_id,
                status=Status.COMPLIANT if has_route else Status.VIOLATION,
                explanation=(
                    "itinéraire d'évacuation détecté" if has_route else "aucun itinéraire décrit"
                ),
            )
        if rule.rule_id == "FIRE-ALARM-ERP":
            if not _is_erp(narrative):
                return not_erp
            has_alarm = "alarme" in narrative
            return Verdict(
                rule_id=rule.rule_id,
                status=Status.COMPLIANT if has_alarm else Status.VIOLATION,
                explanation=(
                    "alarme mentionnée" if has_alarm else "aucune alarme mentionnée"
                ),
            )
        return Verdict(
            rule_id=rule.rule_id, status=Status.NOT_APPLICABLE, explanation="règle inconnue"
        )


# --- Test fixtures -----------------------------------------------------------


class BlindApplier:
    """Mutation proof: always says compliant -> misses every real violation."""

    name = "blind"

    def apply(self, doc: PlanDocument, rule: Rule) -> tuple[Verdict, Usage]:
        return (
            Verdict(rule_id=rule.rule_id, status=Status.COMPLIANT, explanation="(aveugle)"),
            Usage(),
        )


class GoldApplier:
    """Control: replays the gold labels -> perfect, must not be flagged."""

    name = "gold"

    def __init__(self, gold: list[GoldItem]) -> None:
        self._labels = {(g.doc_id, g.rule_id): g.expected for g in gold}

    def apply(self, doc: PlanDocument, rule: Rule) -> tuple[Verdict, Usage]:
        status = self._labels.get((doc.doc_id, rule.rule_id), Status.NOT_APPLICABLE)
        return Verdict(rule_id=rule.rule_id, status=status, explanation="(gold)"), Usage()

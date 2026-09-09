"""Shared contracts for plan-comply. Every module imports from here.

SCOPE: this is NOT a regulatory authority and NOT professional compliance
advice. The documents are SYNTHETIC, the rules are SIMPLIFIED illustrations
loosely inspired by public accessibility/fire-safety concepts, and there is no
client data. The value is the automation instrument -- taking a rule from an
expert's head to a tool that runs in a report AND measuring whether that tool
actually catches violations -- not the regulatory content.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Status(StrEnum):
    """Outcome of applying one rule to one document."""

    COMPLIANT = "compliant"
    VIOLATION = "violation"
    NOT_APPLICABLE = "not_applicable"


class RuleKind(StrEnum):
    """How a rule is checked.

    STRUCTURED rules read a measured field (corridor width, ramp slope) and are
    objectively decidable. JUDGMENT rules read the free-text narrative and need
    an expert's reading -- this is where the LLM earns its place.
    """

    STRUCTURED = "structured"
    JUDGMENT = "judgment"


class Element(BaseModel):
    """A measured element on a plan sheet (a door, a corridor, a ramp...)."""

    kind: str
    label: str
    # Measured attributes, in SI units (metres, percent). Missing = unknown.
    attributes: dict[str, float] = Field(default_factory=dict)


class PlanDocument(BaseModel):
    """A synthetic construction plan sheet: measured elements + a narrative."""

    doc_id: str
    project: str
    discipline: str
    elements: list[Element] = Field(default_factory=list)
    narrative: str = ""


class Rule(BaseModel):
    """A compliance rule as an expert would state it."""

    rule_id: str
    title: str
    # How a compliance expert actually applies it (goes into the LLM prompt).
    statement: str
    kind: RuleKind
    # Minutes a human expert spends applying this rule manually, per document.
    # Used only for the resolution-time framing in the report (illustrative).
    manual_minutes: float = 3.0


class Verdict(BaseModel):
    """The automation's decision for one (document, rule) pair."""

    rule_id: str
    status: Status
    # A quote or measured value that grounds the verdict (the "where/why").
    evidence: str | None = None
    explanation: str = ""


class RuleResult(BaseModel):
    """A verdict plus the operational signal captured while producing it."""

    verdict: Verdict
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class DocumentReport(BaseModel):
    """All rule results for a single document (the shippable artifact)."""

    doc_id: str
    project: str
    results: list[RuleResult] = Field(default_factory=list)

    @property
    def violations(self) -> list[RuleResult]:
        return [r for r in self.results if r.verdict.status is Status.VIOLATION]


class GoldItem(BaseModel):
    """Ground-truth label: what SHOULD the verdict be for this (doc, rule)?"""

    doc_id: str
    rule_id: str
    expected: Status


class ReliabilityReport(BaseModel):
    """How well the automation matches ground truth on the labelled set.

    The headline number for Freeda's world is RECALL ON VIOLATIONS: of the
    violations that truly exist, how many did the automation catch? A missed
    violation (false negative) is the failure that destroys client trust.
    """

    applier_name: str
    total: int
    agree: int
    # Truly a violation, but the automation said compliant/NA -> a MISSED error.
    false_negatives: int
    # Not a violation, but the automation flagged one -> noise for the expert.
    false_positives: int
    # Denominator for recall: how many true violations were in the set.
    true_violations: int

    @property
    def agreement_rate(self) -> float:
        return self.agree / self.total if self.total else 1.0

    @property
    def violation_recall(self) -> float:
        """Caught violations / true violations. 1.0 = missed nothing."""
        if self.true_violations == 0:
            return 1.0
        caught = self.true_violations - self.false_negatives
        return caught / self.true_violations

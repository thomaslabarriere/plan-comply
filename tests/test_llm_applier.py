"""LLM applier path, tested with a stubbed client (no network, no API credits).

Proves the code that actually ships and breaks in production: tool-call
parsing (valid AND malformed), the success mapping to a verdict, and the
fail-safe path -- an API error or an empty response must NEVER be read as
"compliant". The offline default never touches any of this; these tests
monkeypatch `openai.OpenAI` so the LLM applier runs with zero credits.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import openai
import pytest

from plancomply.appliers import LLMApplier
from plancomply.documents import get_document
from plancomply.models import Status
from plancomply.rules import get_rule


def _fake_openai(create_fn: Any) -> Any:
    """A stand-in for openai.OpenAI exposing chat.completions.create."""
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_fn))
    )
    return lambda *a, **k: client


def _tool_completion(args: dict[str, Any]) -> Any:
    call = SimpleNamespace(
        type="function",
        id="call_1",
        function=SimpleNamespace(name="report_verdict", arguments=json.dumps(args)),
    )
    message = SimpleNamespace(tool_calls=[call], content=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=4),
    )


def _applier(monkeypatch: pytest.MonkeyPatch, create_fn: Any) -> LLMApplier:
    monkeypatch.setattr(openai, "OpenAI", _fake_openai(create_fn))
    return LLMApplier(model="gpt-4o", api_key="test-key")


# --- Pure parser: robust to valid and malformed tool-call payloads ----------

def test_parse_accepts_a_valid_payload() -> None:
    rule = get_rule("ACC-RAMP-05")
    v = LLMApplier._parse(
        rule, '{"status": "violation", "evidence": "8%", "explanation": "trop raide"}'
    )
    assert v is not None
    assert v.status is Status.VIOLATION
    assert v.evidence == "8%"


def test_parse_rejects_malformed_payloads() -> None:
    rule = get_rule("ACC-RAMP-05")
    assert LLMApplier._parse(rule, "not json at all") is None       # invalid JSON
    assert LLMApplier._parse(rule, '["a", "b"]') is None            # not an object
    assert LLMApplier._parse(rule, '{"status": "bogus"}') is None   # invalid enum
    assert LLMApplier._parse(rule, '{"explanation": "x"}') is None  # missing status


# --- LLMApplier.apply over the stubbed client -------------------------------

def test_apply_maps_a_toolcall_to_a_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    applier = _applier(
        monkeypatch,
        lambda **kw: _tool_completion(
            {"status": "violation", "evidence": "Rampe 8%", "explanation": "e"}
        ),
    )
    verdict, usage = applier.apply(get_document("doc-3"), get_rule("ACC-RAMP-05"))
    assert verdict.status is Status.VIOLATION
    assert verdict.evidence == "Rampe 8%"
    assert usage.prompt_tokens == 11 and usage.completion_tokens == 4


def test_apply_fails_safe_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**kw: Any) -> Any:
        raise RuntimeError("API is down")

    applier = _applier(monkeypatch, boom)
    verdict, usage = applier.apply(get_document("doc-4"), get_rule("FIRE-ALARM-ERP"))
    # A failed call must never be read as compliant (nor as a confirmed gap).
    assert verdict.status is Status.NOT_APPLICABLE
    assert verdict.status is not Status.COMPLIANT
    assert "erreur" in verdict.explanation.lower()
    assert usage.prompt_tokens == 0


def test_apply_is_undecided_when_no_toolcall(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[], content=None))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=0),
    )
    applier = _applier(monkeypatch, lambda **kw: empty)
    verdict, _ = applier.apply(get_document("doc-1"), get_rule("FIRE-ALARM-ERP"))
    # An empty/malformed response is graceful: undecided, never "compliant".
    assert verdict.status is Status.NOT_APPLICABLE
    assert verdict.status is not Status.COMPLIANT


def test_apply_ignores_malformed_toolcall_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A tool call whose arguments are not parseable must fall through to the
    # fail-safe verdict rather than crashing or being read as compliant.
    applier = _applier(
        monkeypatch, lambda **kw: _tool_completion_raw("report_verdict", "{not json")
    )
    verdict, _ = applier.apply(get_document("doc-1"), get_rule("ACC-CIRC-140"))
    assert verdict.status is Status.NOT_APPLICABLE
    assert verdict.status is not Status.COMPLIANT


def _tool_completion_raw(name: str, arguments: str) -> Any:
    call = SimpleNamespace(
        type="function", id="c1", function=SimpleNamespace(name=name, arguments=arguments)
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call], content=None))],
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=1),
    )

"""plan-comply CLI.

  plan-comply check         [--applier heuristic|llm] [--doc doc-1] [--json out.json]
  plan-comply reliability   [--applier heuristic|llm]

Offline by default (heuristic baseline). With --applier llm you need
OPENAI_API_KEY (or OPENROUTER_API_KEY + --provider openrouter) -- that is the
only thing required to run the real automation.
"""

from __future__ import annotations

import argparse
import json
import sys

from .appliers import Applier, HeuristicApplier, LLMApplier
from .documents import get_document, load_corpus
from .goldset import build_gold_set
from .models import Status
from .reliability import evaluate_reliability
from .report import render_document_report, render_reliability_report
from .rules import RULES
from .runner import run_document


def _build_applier(args: argparse.Namespace) -> Applier:
    if args.applier == "llm":
        return LLMApplier(model=args.model, provider=args.provider)
    return HeuristicApplier()


def _add_applier_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--applier", choices=["heuristic", "llm"], default="heuristic")
    p.add_argument("--provider", choices=["openai", "openrouter"], default="openai")
    p.add_argument("--model", default="gpt-4o")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="plan-comply",
        description="Automate construction compliance-rule checking + measure its reliability.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run the automation on documents and print a report.")
    _add_applier_flags(check)
    check.add_argument("--doc", help="A single doc_id (default: whole corpus).")
    check.add_argument("--json", help="Also write the report(s) as JSON to this path.")

    rel = sub.add_parser("reliability", help="Measure the automation against the gold set.")
    _add_applier_flags(rel)

    args = parser.parse_args(argv)
    applier = _build_applier(args)

    if args.command == "check":
        docs = [get_document(args.doc)] if args.doc else load_corpus()
        reports = [run_document(applier, doc, RULES) for doc in docs]
        for report in reports:
            print(render_document_report(report))
            print()
        total_violations = sum(len(r.violations) for r in reports)
        print(f"Total: {total_violations} violation(s) sur {len(docs)} document(s).")
        if args.json:
            payload = [r.model_dump(mode="json") for r in reports]
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            print(f"\nJSON écrit dans {args.json}")
        return 0

    if args.command == "reliability":
        rel_report = evaluate_reliability(applier, build_gold_set())
        print(render_reliability_report(rel_report))
        # Non-zero exit if the automation missed any real violation -- useful in CI.
        return 1 if rel_report.false_negatives > 0 else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())


# Re-exported for tests / callers that want the enum without a deep import.
__all__ = ["main", "Status"]

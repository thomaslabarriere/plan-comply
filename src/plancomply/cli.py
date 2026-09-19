"""plan-comply CLI.

  plan-comply check        [--applier heuristic|llm] [--doc ID | --pdf F | --image F] [--json OUT]
  plan-comply reliability  [--applier heuristic|llm]
  plan-comply compare      [--model M]     # offline baseline vs LLM, side by side

Offline by default (heuristic baseline). The LLM applier, `--image` ingestion,
and `compare` need OPENAI_API_KEY (or OPENROUTER_API_KEY + --provider
openrouter) -- that is the only thing required to run the real automation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .appliers import Applier, HeuristicApplier, LLMApplier
from .documents import get_document, load_corpus
from .goldset import build_gold_set
from .models import Status
from .reliability import compare_reliability, evaluate_reliability
from .report import (
    render_document_report,
    render_reliability_comparison,
    render_reliability_report,
)
from .rules import RULES
from .runner import run_document


def _build_applier(args: argparse.Namespace) -> Applier:
    if args.applier == "llm":
        _require_key(args.provider)
        return LLMApplier(model=args.model, provider=args.provider)
    return HeuristicApplier()


def _add_applier_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--applier", choices=["heuristic", "llm"], default="heuristic")
    p.add_argument("--provider", choices=["openai", "openrouter"], default="openai")
    p.add_argument("--model", default="gpt-4o")


def _require_key(provider: str) -> None:
    var = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
    if not os.environ.get(var):
        raise SystemExit(
            f"{var} is not set. The LLM applier needs it; set it and re-run "
            "(or use the offline heuristic applier)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="plan-comply",
        description="Automate construction compliance-rule checking + measure its reliability.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run the automation on documents and print a report.")
    _add_applier_flags(check)
    check.add_argument("--doc", help="A single doc_id from the built-in corpus.")
    check.add_argument("--pdf", help="Ingest a plan-sheet PDF instead of the corpus.")
    check.add_argument("--image", help="Ingest a plan-sheet image via a vision model (needs key).")
    check.add_argument("--json", help="Also write the report(s) as JSON to this path.")

    rel = sub.add_parser("reliability", help="Measure the automation against the gold set.")
    _add_applier_flags(rel)
    rel.add_argument(
        "--min-recall",
        type=float,
        default=0.8,
        help=(
            "Violation-recall floor for the CI gate (default 0.8). The automation "
            "is deliberately imperfect, so the gate guards against REGRESSION below "
            "this documented level rather than demanding a perfect 100%%."
        ),
    )

    cmp = sub.add_parser(
        "compare",
        help="Compare the offline baseline against the LLM automation (needs a key).",
    )
    cmp.add_argument("--provider", choices=["openai", "openrouter"], default="openai")
    cmp.add_argument("--model", default="gpt-4o")

    args = parser.parse_args(argv)

    if args.command == "compare":
        _require_key(args.provider)
        gold = build_gold_set()
        comparison = compare_reliability(
            [HeuristicApplier(), LLMApplier(model=args.model, provider=args.provider)],
            gold,
        )
        print(render_reliability_comparison(comparison))
        return 0

    applier = _build_applier(args)

    if args.command == "check":
        if args.pdf:
            from .ingest import PdfIngestor

            docs = [PdfIngestor().ingest(args.pdf)]
        elif args.image:
            from .ingest import VisionIngestor

            _require_key(args.provider)
            docs = [VisionIngestor(model=args.model, provider=args.provider).ingest(args.image)]
        elif args.doc:
            docs = [get_document(args.doc)]
        else:
            docs = load_corpus()
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
        # Regression gate: the automation is knowingly imperfect (see appliers.py),
        # so CI fails only if recall drops BELOW the documented floor, not on every
        # miss. This keeps the gate honest -- it protects the measured level from
        # silently degrading -- without pinning CI red at a demo's realistic recall.
        if rel_report.violation_recall < args.min_recall:
            print(
                f"\nGATE ÉCHOUÉ: recall {rel_report.violation_recall * 100:.0f}% "
                f"< plancher {args.min_recall * 100:.0f}% (régression détectée)."
            )
            return 1
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())


# Re-exported for tests / callers that want the enum without a deep import.
__all__ = ["main", "Status"]

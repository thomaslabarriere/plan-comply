# plan-comply

**End-to-end automation of construction compliance-rule checking — with a false-negative reliability instrument.**

A compliance tool that ships into a real report is only trustworthy if you can say how often it **misses a real violation**. `plan-comply` takes a compliance rule the way an expert states it, applies it to a parsed plan document, and produces a shippable verdict (compliant / violation / not-applicable, with evidence). Then — the part most demos skip — it measures the automation against a labelled gold set and reports its **violation recall**: of the violations that truly exist, how many did it catch?

> **Scope.** Not a regulatory authority, not professional compliance advice. Documents are **synthetic**, rules are **simplified illustrations** loosely inspired by public accessibility/fire-safety concepts, and there is no client data. The value is the automation instrument — and the honesty of measuring its false negatives — not the regulatory content. Plug in the real rule base and your own documents for real numbers.

## Quick start (no API key needed)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Run the offline baseline automation on the synthetic corpus:
plan-comply check

# Measure how reliably it catches real violations:
plan-comply reliability
```

The offline **heuristic baseline** (measured field checks + narrative keyword rules) lets the whole pipeline — including the reliability instrument — run with no API key.

## Run the real automation (LLM)

```bash
export OPENAI_API_KEY=sk-...          # the only thing needed to go live
plan-comply check       --applier llm --model gpt-4o
plan-comply reliability --applier llm --model gpt-4o
# OpenRouter: --applier llm --provider openrouter --model anthropic/claude-3.7-sonnet
```

With a key, an LLM applies each rule to the document and returns a structured verdict; the reliability command then scores that automation against the same gold set.

## What it produces

A per-document **compliance report** — the shippable artifact — plus the operational framing a delivery team cares about (manual minutes saved, automated seconds, tokens). Here is the **offline baseline** on `doc-4` (an ERP whose narrative says it mentions *no* alarm):

```
Rapport de conformité — Halle commerciale Saint-Roch [doc-4]
Violations: 1 / 5 règles vérifiées
!! ACC-DOOR-090 — Passage utile de porte
OK FIRE-ALARM-ERP — Alarme incendie en ERP
      alarme mentionnée
Temps de résolution
  Manuel (estimé): 17 min
  Automatisé: 0.00 s
```

Notice the baseline passes `FIRE-ALARM-ERP` — it "saw" the word *alarme* inside *"aucun ... d'alarme"*. A convincing demo would stop here. The point of this project is the next section: **catching that the automation is wrong.**

## Why you can trust the automation (the differentiator)

The **reliability instrument** grades the automation against a labelled gold set and reports the number that matters for compliance — **violation recall** (a missed violation is the false negative that destroys client trust):

```
Fiabilité de l'automatisation — heuristic
Recall sur violations: 80% (4/5 détectées)
Violations manquées (faux négatifs): 1
Fausses alertes (faux positifs): 0
```

That 80% is real and instructive: the keyword baseline **cannot handle negation** — a document saying an ERP mentions *no* alarm still contains the word "alarme", so the baseline wrongly passes it. The instrument names that one miss. Swap in the LLM applier (`--applier llm`) and re-measure to see whether it closes the gap — which is exactly the question you'd ask before shipping either one.

`plan-comply reliability` exits non-zero when the automation missed any real violation, so it drops straight into CI.

## Why you can trust the instrument (mutation proof)

`tests/` asserts that the reliability instrument itself is correct: a **blind** automation (always "compliant") is caught with recall 0 and every violation counted as missed; a **perfect** automation is not falsely flagged (recall 1, zero false positives); the baseline's known false-negative gap is reported exactly; and a raising applier is isolated per-rule, never crashing the run.

```bash
ruff check src tests
mypy
pytest
```

## Layout

```
src/plancomply/
  models.py        # shared contracts (pydantic)
  documents.py     # synthetic plan sheets + parser (OCR/vision plugs in here)
  rules.py         # compliance rules + deterministic reference checks
  goldset.py       # ground-truth labels (objective for structured, hand for judgment)
  appliers.py      # LLM applier + offline baseline + test fixtures
  runner.py        # apply rules to documents, capture latency/usage
  reliability.py   # violation recall / false negatives / false positives
  report.py        # render the report + reliability artifacts
  cli.py           # plan-comply check | reliability
tests/             # mutation-proof + control + parser/gold-set guards
```

## License

MIT

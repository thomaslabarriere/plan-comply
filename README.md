# plan-comply

**End-to-end automation of construction compliance-rule checking, with a false-negative reliability instrument.**

A compliance tool that ships into a real report is only trustworthy if you can say how often it **misses a real violation**. `plan-comply` takes a compliance rule the way an expert states it, applies it to a parsed plan document, and produces a shippable verdict (compliant / violation / not-applicable, with evidence). Then, the part most demos skip, it measures the automation against a labelled gold set and reports its **violation recall**: of the violations that truly exist, how many did it catch?

> **Scope.** Not a regulatory authority, not professional compliance advice. Documents are **synthetic**, rules are **simplified illustrations** loosely inspired by public accessibility/fire-safety concepts, and there is no client data. The value is the automation instrument, and the honesty of measuring its false negatives, not the regulatory content. Plug in the real rule base and your own documents for real numbers.

## Quick start (no API key needed)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Run the offline baseline automation on the synthetic corpus:
plan-comply check

# Measure how reliably it catches real violations:
plan-comply reliability
```

The offline **heuristic baseline** (measured field checks + narrative keyword rules) lets the whole pipeline, including the reliability instrument, run with no API key.

## Run the real automation (LLM)

```bash
export OPENAI_API_KEY=sk-...          # the only thing needed to go live
plan-comply check       --applier llm --model gpt-4o
plan-comply reliability --applier llm --model gpt-4o
# OpenRouter: --applier llm --provider openrouter --model anthropic/claude-3.7-sonnet
```

With a key, an LLM applies each rule to the document and returns a structured verdict; the reliability command then scores that automation against the same gold set, and prints per-document **inference cost** (illustrative $/doc) and **latency** alongside the recall.

### Does the LLM beat the baseline? (`compare`)

The question you actually ask before shipping, does the LLM automation close the false-negative gap the cheap baseline leaves open?, is one command:

```bash
plan-comply compare --model gpt-4o     # baseline vs LLM, side by side (needs a key)
```

```
════════════════════════════════════════════════════════════════
Comparaison de fiabilité (recall sur violations)
────────────────────────────────────────────────────────────────
  applier          recall   manquées   fausses alertes
  heuristic          80%          1                0
  llm:gpt-4o         ...%        ...              ...
════════════════════════════════════════════════════════════════
```

The `heuristic` row is the measured offline baseline (80%, one miss). The `llm:gpt-4o` row is filled in when you run it with a key, how much it closes the gap depends on the model and the run, so no number is claimed here.

### Ingest a real document (PDF / vision)

The corpus is the trivial ingestor; two real ones sit behind the same interface (`src/plancomply/ingest.py`):

```bash
plan-comply check --pdf examples/plan-doc-1.pdf          # document parsing, offline
plan-comply check --image plan-sheet.png --model gpt-4o  # vision model (needs a key)
```

`--pdf` extracts text (pypdf) and parses it; `--image` sends the sheet to a vision model that returns the structured elements + narrative. A production OCR/layout pipeline drops in here without touching the rules or the reliability instrument.

## What it produces

A per-document **compliance report**, the shippable artifact, plus the operational framing a delivery team cares about (manual minutes saved, automated seconds, tokens). Verbatim output of `plan-comply check --doc doc-4` on the **offline baseline** (an ERP whose narrative says it mentions *no* alarm):

```
────────────────────────────────────────────────────────────────
Rapport de conformité: Halle commerciale Saint-Roch [doc-4]
────────────────────────────────────────────────────────────────
Violations: 1 / 5 règles vérifiées

OK ACC-CIRC-140: Largeur de circulation
      contrôle mesuré
!! ACC-DOOR-090: Passage utile de porte
      contrôle mesuré
OK ACC-RAMP-05: Pente de rampe
      contrôle mesuré
OK FIRE-EVAC-ROUTE: Itinéraire d'évacuation
      itinéraire d'évacuation détecté
OK FIRE-ALARM-ERP: Alarme incendie en ERP
      alarme mentionnée

Temps de résolution
  Manuel (estimé): 17 min
  Automatisé: 0.00 s
────────────────────────────────────────────────────────────────

Total: 1 violation(s) sur 1 document(s).
```

Notice the baseline passes `FIRE-ALARM-ERP`, it "saw" the word *alarme* inside *"aucun ... d'alarme"*. A convincing demo would stop here. The point of this project is the next section: **catching that the automation is wrong.**

## Why you can trust the automation (the differentiator)

The **reliability instrument** grades the automation against a labelled gold set and reports the number that matters for compliance, **violation recall** (a missed violation is the false negative that destroys client trust):

```
────────────────────────────────────────────────────────────────
Fiabilité de l'automatisation: heuristic
────────────────────────────────────────────────────────────────
Recall sur violations: 80% (4/5 détectées)
Violations manquées (faux négatifs): 1
Fausses alertes (faux positifs): 0
Accord global: 96% (24/25)
────────────────────────────────────────────────────────────────
```

The gold set is **independent** ground truth: every label in `goldset.py` is hand-authored by reading each document, never computed from the same reference checks the applier runs. So this agreement is two independent opinions meeting, not the code grading itself, and the numbers mean what they claim.

That 80% is real and instructive: the keyword baseline **cannot handle negation**, a document saying an ERP mentions *no* alarm still contains the word "alarme", so the baseline wrongly passes it. The instrument names that one miss. Swap in the LLM applier (`--applier llm`) and re-measure to see whether it closes the gap, which is exactly the question you'd ask before shipping either one.

CI runs `plan-comply reliability` as a **regression gate**: because the automation is knowingly imperfect, the gate fails only if recall drops **below a documented floor** (`--min-recall`, default `0.8`), not on every miss. It protects the measured level from silently degrading without pinning the build red at a demo's realistic recall.

`plan-comply reliability` exits non-zero when the automation missed any real violation, so it drops straight into CI.

## Why you can trust the instrument (mutation proof)

`tests/` asserts that the reliability instrument itself is correct: a **blind** automation (always "compliant") is caught with recall 0 and every violation counted as missed; a **perfect** automation is not falsely flagged (recall 1, zero false positives); the baseline's known false-negative gap is reported exactly; and a raising applier is isolated per-rule, never crashing the run.

```bash
ruff check src tests
mypy
pytest
```

## From an expert interview to a running check

The workflow this is built around, turning a compliance expert's words into an actionable brief, then an encoded rule with a ground-truth label, is written up in [`docs/from-expert-to-rule.md`](docs/from-expert-to-rule.md).

## Layout

```
src/plancomply/
  models.py        # shared contracts (pydantic)
  documents.py     # synthetic plan sheets + text parser
  ingest.py        # real ingestion: PDF (pypdf) + vision model, one interface
  rules.py         # compliance rules + deterministic reference checks
  goldset.py       # independent hand-authored ground-truth labels (not derived from the applier)
  appliers.py      # LLM applier + offline baseline + test fixtures
  runner.py        # apply rules to documents, capture latency/usage
  reliability.py   # violation recall / false negatives / false positives + compare
  pricing.py       # illustrative token pricing for the $/doc line
  report.py        # render the report, reliability, and comparison artifacts
  cli.py           # plan-comply check | reliability | compare
scripts/           # regenerate the sample PDF fixture
examples/          # committed sample plan-sheet PDF
docs/              # expert-interview -> rule write-up
tests/             # mutation-proof + control + parser/gold-set/ingest guards
```

## License

MIT

# Decisions

Why this automation and its reliability instrument are shaped the way they are.
Each entry is a fork I actually hit, the options I weighed, what I chose, and
what the choice still does **not** prove. The code is the *what*; this is the
*why*. For a compliance tool, the judgement about how it can miss a real
violation is the product as much as the checking itself.

---

## 1. The headline metric is violation RECALL (false negatives), not accuracy

**Fork.** Report the automation's overall accuracy (how often its verdict is
right), or report specifically how many *real violations* it caught.

**Chosen.** Violation recall. `reliability.py` measures, over a labelled gold
set, the share of true violations the automation flagged: a missed violation
(false negative) is the number that matters. Accuracy and precision are reported
too, but recall on violations is the headline.

**Why.** For a verification product, the catastrophic failure is the one that
ships a "compliant" report over a plan that wasn't: a missed error on the
construction site, not a false alarm. Accuracy hides that: a tool can be 95%
accurate and still miss the one violation that destroys client trust. Optimising
or even *reporting* the wrong metric is how a checking pipeline lies to itself.

**Doesn't prove.** Recall on a small synthetic gold set, not a population
estimate on real plans; it shows the instrument measures the right thing, not a
production reliability figure.

---

## 2. The gold set is decoupled from the automation's own logic

**Fork.** Label the gold set from what the checker outputs (cheap), or author the
ground-truth labels independently of the code being graded.

**Chosen.** Independent. `goldset.py` labels each (document, rule) pair from what
the rule *actually requires*, not from what the applier happens to return, so the
recall number is not graded against the tool's own opinion.

**Why.** A gold set derived from the code measures self-consistency, not truth.
It would score high by construction and prove nothing. Decoupling is what makes
the false-negative count real.

**Doesn't prove.** The labels are mine, on simplified rules; a real deployment
needs a compliance expert's labels on the real rule base.

---

## 3. A kept, honest false negative: the baseline is negation-blind (recall 80%)

**Fork.** Tune the baseline until the demo shows 100% recall, or ship the real
number with its failure visible.

**Chosen.** Ship the real number. The offline heuristic baseline scores **recall
80% (4/5), one missed violation, zero false positives**. It misses a violation
phrased with a negation ("aucun détecteur d'alarme" contains the keyword "alarme",
so a keyword rule reads it as satisfied). That miss is left in, surfaced by the
instrument, not patched away.

**Why.** The whole point is to measure false negatives honestly; hiding the one
my own baseline has would be the exact self-deception the tool exists to prevent.
It also shows the failure mode a naive keyword checker really has, which is the
argument for the LLM applier.

**Doesn't prove.** One negation case on a tiny corpus; a real negation-handling
evaluation needs many, adversarially phrased.

---

## 4. Not-applicable is excluded from the score, never counted as a win

**Fork.** When a rule doesn't apply to a document, count it as a "pass" (inflates
the score) or exclude it from the applicable denominator.

**Chosen.** Exclude it. `reliability.py` / `report.py` compute rates over the
*applicable* (document, rule) pairs only; NA verdicts never pad the numbers.

**Why.** Counting non-applicable rules as successes is the cheapest way to make a
compliance tool look better than it is: a checker that calls everything NA would
score perfectly. Excluding them keeps the recall honest.

**Doesn't prove.** Correct NA classification itself is assumed here; mislabelling
a real violation as NA would be its own (unmeasured) failure mode.

---

## 5. A rule that crashes is never read as "compliant"

**Fork.** On an applier error, default the verdict to compliant (fail-open),
violation (fail-closed), or an explicit error state.

**Chosen.** Never compliant. An applier/rule that raises is isolated and does not
produce a silent "compliant"; the failure is surfaced, not swallowed into a
green report.

**Why.** Fail-open is the most dangerous default for verification: a crashed check
that reads as "all good" is exactly the missed-violation-behind-a-green-report
failure. `plan-comply reliability` also exits non-zero when recall is below the
bar, so a regression gates CI rather than shipping quietly.

**Doesn't prove.** Error isolation, not the correctness of every rule's own logic.

---

## 6. Offline heuristic baseline by default; the LLM applier is one swap away

**Fork.** Require an API key to run anything, or run the whole pipeline (including
the reliability instrument) offline and light up the LLM applier only with a key.

**Chosen.** Offline by default. A measured-field + keyword **heuristic baseline**
runs the full pipeline with zero network; `--applier llm` swaps in the real model
behind the same interface, and the run compares baseline vs LLM with cost/latency.

**Why.** A reviewer must see the whole thesis (automation + false-negative
measurement) in two minutes, deterministically, no credits; the baseline's
honest 80% is the foil that shows what the LLM has to beat.

**Doesn't prove.** The baseline is deliberately weak; the meaningful number is the
LLM applier's recall on a real rule base, which is not measured here (no LLM run
is committed). The `compare` command wires the LLM applier in behind a key so that
number can be produced against real data.

---

## 7. OCR/vision is a seam, not a claim

**Fork.** Fake plan parsing with hand-fed structured data, or expose a real
ingestion seam.

**Chosen.** A seam. `ingest.py` / `documents.py` parse a plan sheet behind a
`parse_plan_sheet` interface with a pluggable OCR/vision step; the synthetic
corpus feeds it structured content, and a real vision model drops in unchanged.

**Why.** Honest about where the toy ends: the value on offer is the automation +
false-negative instrument, and it is ready to sit behind real plan ingestion,
not a claim that I have solved BTP plan OCR.

**Doesn't prove.** It has not been run on real architectural plans; the vision
step is wired but not validated on production documents.

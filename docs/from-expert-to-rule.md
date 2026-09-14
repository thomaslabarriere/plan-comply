# From an expert interview to a running check

The brief we work from: *"You come out of an expert interview with a technically actionable brief, not a vague wishlist."* This is how one rule in this repo actually got there — the workflow the automation is built around, not an afterthought.

## 1. What the expert says (raw)

> "On regarde toujours si les circulations sont assez larges. Pour un ERP, une
> circulation commune, faut au moins un mètre quarante de large sinon un
> fauteuil roulant ne passe pas et on le refuse. C'est le premier truc que je
> vérifie, ça prend deux minutes mais c'est systématique."

Vague-wishlist version would stop here ("automate width checks"). The actionable brief pins down the four things an engineer needs.

## 2. The actionable brief (what I extract)

| Question to the expert | Answer that makes it codeable |
|---|---|
| What is measured? | The **clear width** of a common circulation, in metres. |
| What is the threshold and direction? | `>= 1.40 m`. Below → **violation**. |
| Where does the value live in the document? | A `corridor` element's `width_m` field. |
| When does the rule *not* apply? | No `corridor` element on the sheet → **not applicable** (not a pass). |
| How is it decided today, and how long? | Eye + ruler on the plan, ~2 min/sheet, systematic. |

That last row is not paperwork — it is the **resolution-time** baseline the report later reports against, and it tells you whether automating this rule is even worth it.

## 3. The encoded rule (what ships)

The brief maps one-to-one onto the codebase:

```python
# rules.py — the statement the LLM applier reads, expert's words made precise
Rule(
    rule_id="ACC-CIRC-140",
    title="Largeur de circulation",
    statement="Toute circulation horizontale commune doit offrir une largeur "
              "libre d'au moins 1,40 m ... En-dessous, c'est une violation.",
    kind=RuleKind.STRUCTURED,
    manual_minutes=2.0,           # the "~2 min" from the interview
)

# rules.py — the objective reference check (the applier's structured path)
"ACC-CIRC-140": lambda d: _check_min_attr(d, "corridor", "width_m", 1.40)
```

The gold-set label for this rule is written out **independently by hand** in
`goldset.py` (doc-2's 1,20 m corridor → `VIOLATION`, and so on). It is not
generated from this reference check — if it were, the reported agreement would
partly be the code grading itself. A regression test keeps the hand labels and
the corpus in sync so a document edit that invalidates a label fails loudly.

- **STRUCTURED vs JUDGMENT** comes straight from the interview: a measured field → structured (objectively checkable); "does the narrative describe an evacuation route" → judgment (needs the LLM). Being honest about which is which is the whole point — you don't dress up a lookup as AI, and you don't pretend a judgment call is objective.
- The **not-applicable** answer is encoded explicitly, because silently passing a sheet that has no corridor is exactly the kind of hidden false negative this project exists to catch.

## 4. Then: prove it, don't trust it

Every encoded rule gets a ground-truth label in `goldset.py` and is run through the reliability instrument. The brief above is only "done" (the brief's word) when the automation's **violation recall** on that rule is measured — not when the code merely runs.

"""Synthetic plan-sheet documents + a parser.

The parser turns a semi-structured plan-sheet text into a PlanDocument. It is a
deliberately simple, deterministic ingestion layer -- the point is that it sits
behind one interface (`parse_plan_sheet`), so a real OCR / document-parsing /
vision pipeline drops in here without touching the rest of the automation.

All documents below are INVENTED for evaluation. No real project data.
"""

from __future__ import annotations

from .models import Element, PlanDocument

# A plan sheet is written as a small header block, an ELEMENTS table (one line
# per element: "kind | label | attr=value, attr=value"), and a NARRATIVE block.
# This mirrors what an OCR/extraction step would hand off downstream.


def parse_plan_sheet(text: str) -> PlanDocument:
    """Parse a plan-sheet text into a PlanDocument.

    Sections are marked by lines '# HEADER', '# ELEMENTS', '# NARRATIVE'.
    Unknown attribute values that are not numbers are ignored (kept out of the
    numeric attributes map) rather than crashing the ingestion.
    """
    header: dict[str, str] = {}
    elements: list[Element] = []
    narrative_lines: list[str] = []
    section = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip().upper()
            continue
        if section == "HEADER":
            if ":" in line:
                key, _, value = line.partition(":")
                header[key.strip().lower()] = value.strip()
        elif section == "ELEMENTS":
            elements.append(_parse_element(line))
        elif section == "NARRATIVE":
            narrative_lines.append(line)

    return PlanDocument(
        doc_id=header.get("doc_id", "unknown"),
        project=header.get("project", "unknown"),
        discipline=header.get("discipline", "unknown"),
        elements=elements,
        narrative=" ".join(narrative_lines),
    )


def _parse_element(line: str) -> Element:
    parts = [p.strip() for p in line.split("|")]
    kind = parts[0] if parts else ""
    label = parts[1] if len(parts) > 1 else ""
    attributes: dict[str, float] = {}
    if len(parts) > 2:
        for pair in parts[2].split(","):
            key, _, value = pair.partition("=")
            key = key.strip()
            try:
                attributes[key] = float(value.strip())
            except ValueError:
                continue
    return Element(kind=kind, label=label, attributes=attributes)


# --- The synthetic corpus ----------------------------------------------------
# Written as raw plan sheets so the parser is exercised end to end.

_SHEETS: list[str] = [
    # doc-1: compliant on structure, evacuation described, ERP with alarm.
    """
# HEADER
doc_id: doc-1
project: Groupe scolaire Lavoisier
discipline: Accessibilité / Sécurité
# ELEMENTS
corridor | Couloir RDC | width_m=1.60
door | Porte salle 12 | clear_width_m=0.93
ramp | Rampe entrée | slope_pct=4.0
# NARRATIVE
Le rez-de-chaussée est un ERP de catégorie 4. Un itinéraire d'évacuation
balisé conduit du hall vers la sortie de secours située côté cour. Le bâtiment
est équipé d'un système de sécurité incendie avec alarme sonore de type 2b.
""",
    # doc-2: corridor too narrow (structural violation), rest fine.
    """
# HEADER
doc_id: doc-2
project: Résidence Les Tilleuls
discipline: Accessibilité
# ELEMENTS
corridor | Couloir R+1 | width_m=1.20
door | Porte T3 | clear_width_m=0.90
ramp | Rampe parking | slope_pct=5.0
# NARRATIVE
Logements collectifs, non ERP. Les cheminements desservent les logements du
premier étage.
""",
    # doc-3: ramp too steep AND no evacuation route described.
    """
# HEADER
doc_id: doc-3
project: Médiathèque du Parc
discipline: Accessibilité / Sécurité
# ELEMENTS
corridor | Galerie | width_m=2.00
door | Entrée principale | clear_width_m=1.20
ramp | Rampe extérieure | slope_pct=8.0
# NARRATIVE
Établissement recevant du public. Le document décrit l'aménagement intérieur
et le mobilier. Un dispositif d'alarme incendie généralisée est prévu.
""",
    # doc-4: door too narrow, ERP without any alarm mention.
    """
# HEADER
doc_id: doc-4
project: Halle commerciale Saint-Roch
discipline: Accessibilité / Sécurité
# ELEMENTS
corridor | Allée centrale | width_m=1.80
door | Sas d'entrée | clear_width_m=0.82
ramp | Rampe livraison | slope_pct=3.5
# NARRATIVE
Halle commerciale ouverte au public (ERP type M). Un itinéraire d'évacuation
mène vers les deux sorties de secours signalées. Le document ne mentionne
aucun équipement de détection ou d'alarme.
""",
    # doc-5: fully compliant, non-ERP dwelling (fire rules N/A or satisfied).
    """
# HEADER
doc_id: doc-5
project: Maison individuelle Bergerac
discipline: Accessibilité
# ELEMENTS
corridor | Dégagement | width_m=1.45
door | Porte séjour | clear_width_m=0.95
ramp | Rampe jardin | slope_pct=4.5
# NARRATIVE
Maison individuelle, non ERP. Les circulations et l'accès de plain-pied sont
conformes aux dimensions requises.
""",
]


def load_corpus() -> list[PlanDocument]:
    """Parse and return the synthetic plan-sheet corpus."""
    return [parse_plan_sheet(sheet) for sheet in _SHEETS]


def get_document(doc_id: str) -> PlanDocument:
    for doc in load_corpus():
        if doc.doc_id == doc_id:
            return doc
    raise KeyError(f"unknown document {doc_id!r}")

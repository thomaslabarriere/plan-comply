"""Ingestion: PDF round-trip on the committed fixture + vision JSON mapping.

Neither test hits the network: the PDF fixture is committed, and the vision
mapper is tested directly on a JSON payload (the model call is not exercised).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plancomply.documents import get_document
from plancomply.ingest import PdfIngestor, document_from_json
from plancomply.models import Status
from plancomply.rules import REFERENCE_CHECKS

_FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "plan-doc-1.pdf"


def test_pdf_ingestor_round_trips_the_sample_sheet() -> None:
    if not _FIXTURE.exists():
        pytest.skip("run scripts/make_sample_pdf.py to generate the fixture")
    doc = PdfIngestor().ingest(str(_FIXTURE))
    ref = get_document("doc-1")
    assert doc.doc_id == ref.doc_id
    assert doc.project == ref.project
    corridor = next(e for e in doc.elements if e.kind == "corridor")
    assert corridor.attributes["width_m"] == 1.60
    # The parsed PDF drives the same objective checks as the in-memory corpus.
    assert REFERENCE_CHECKS["ACC-CIRC-140"](doc) is Status.COMPLIANT


def test_vision_json_mapping_is_defensive() -> None:
    payload = """
    {
      "project": "Test",
      "discipline": "Accessibilité",
      "elements": [
        {"kind": "corridor", "label": "C1", "attributes": {"width_m": 1.2, "note": "n/a"}},
        {"kind": "door", "label": "D1", "attributes": {"clear_width_m": true}},
        "garbage"
      ],
      "narrative": "ERP avec alarme."
    }
    """
    doc = document_from_json(payload)
    assert doc.project == "Test"
    corridor = next(e for e in doc.elements if e.kind == "corridor")
    assert corridor.attributes == {"width_m": 1.2}  # non-numeric "note" dropped
    door = next(e for e in doc.elements if e.kind == "door")
    assert door.attributes == {}  # bool is not a valid measurement
    assert len(doc.elements) == 2  # the "garbage" string entry is skipped


def test_vision_json_mapping_survives_malformed_payload() -> None:
    doc = document_from_json("not json at all")
    assert doc.project == "unknown"
    assert doc.elements == []

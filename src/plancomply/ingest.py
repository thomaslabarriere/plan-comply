"""Document ingestion: turn a real file into a PlanDocument.

This is the "combine AI building blocks" layer. Two real ingestors sit behind
one `Ingestor` interface, so the rest of the automation never changes:

- `PdfIngestor` — document parsing: extract a PDF's text (pypdf), then the
  plan-sheet parser. Offline, no key.
- `VisionIngestor` — a vision model reads a plan-sheet IMAGE and returns the
  structured elements + narrative. Needs an API key.

The built-in synthetic corpus (documents.py) is the third, trivial ingestor.
Swap in a production OCR/layout pipeline behind this same interface.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Protocol

from .documents import parse_plan_sheet
from .models import Element, PlanDocument


class Ingestor(Protocol):
    name: str

    def ingest(self, source: str) -> PlanDocument: ...


class PdfIngestor:
    """Extract text from a PDF and parse it as a plan sheet (offline)."""

    name = "pdf"

    def ingest(self, source: str) -> PlanDocument:
        from pypdf import PdfReader

        reader = PdfReader(source)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return parse_plan_sheet(text)


_VISION_SYSTEM = (
    "Tu extrais la structure d'une fiche de plan de construction depuis une image. "
    "Renvoie UNIQUEMENT un JSON avec les clés: project (str), discipline (str), "
    "elements (liste d'objets {kind, label, attributes}), narrative (str). "
    "Dans attributes, mets les mesures numériques (ex: width_m, clear_width_m, "
    "slope_pct) en unités SI. N'invente aucune mesure absente de l'image."
)


class VisionIngestor:
    """Read a plan-sheet image with a vision model (needs OPENAI_API_KEY)."""

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        self.name = f"vision:{model}"
        self._model = model
        if base_url is None and provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        if api_key is None:
            api_key = os.environ.get(
                "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def ingest(self, source: str) -> PlanDocument:
        data = base64.b64encode(Path(source).read_bytes()).decode("ascii")
        suffix = Path(source).suffix.lstrip(".").lower() or "png"
        completion = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extrais la fiche de plan."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{suffix};base64,{data}"},
                        },
                    ],
                },
            ],
        )
        content = completion.choices[0].message.content if completion.choices else None
        return document_from_json(content or "{}")


def document_from_json(payload: str) -> PlanDocument:
    """Map a vision model's JSON payload to a PlanDocument (defensively).

    Kept separate from the network call so the mapping is unit-testable without
    an API key. Malformed pieces are dropped rather than crashing ingestion.
    """
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    elements: list[Element] = []
    for raw in data.get("elements", []) or []:
        if not isinstance(raw, dict):
            continue
        attributes: dict[str, float] = {}
        for key, value in (raw.get("attributes") or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                attributes[str(key)] = float(value)
        elements.append(
            Element(
                kind=str(raw.get("kind", "")),
                label=str(raw.get("label", "")),
                attributes=attributes,
            )
        )

    return PlanDocument(
        doc_id=str(data.get("doc_id", "ingested")),
        project=str(data.get("project", "unknown")),
        discipline=str(data.get("discipline", "unknown")),
        elements=elements,
        narrative=str(data.get("narrative", "")),
    )

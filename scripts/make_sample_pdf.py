"""Regenerate the sample plan-sheet PDF fixture from the synthetic corpus.

Run: python scripts/make_sample_pdf.py
Requires the dev extra (fpdf2). The output is committed so `PdfIngestor` and
its round-trip test run without regenerating.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from plancomply.documents import sample_sheet

OUT = Path(__file__).resolve().parent.parent / "examples" / "plan-doc-1.pdf"


def main() -> None:
    sheet = sample_sheet("doc-1")
    pdf = FPDF()
    pdf.set_margins(12, 12, 12)
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    for line in sheet.strip().splitlines():
        # latin-1 is enough for the sample; keep the core-font path dependency-free.
        safe = line.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(pdf.epw, 6, safe or " ")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

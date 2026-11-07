"""
Homily Manager - export homilies to a Word document.

Builds a single .docx from a list of homilies: each with its title, its place in
the Church's year, its readings, and its full text, one per page. Word can open
it, and "Save as PDF" turns it into a PDF; the app also offers a print view for
saving straight to PDF from the browser.
"""

import io
import re

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

READING_LABELS = {
    "first_reading": "First reading", "psalm": "Responsorial psalm",
    "second_reading": "Second reading", "gospel": "Gospel", "other": "Other",
}
READING_ORDER = ["first_reading", "psalm", "second_reading", "gospel", "other"]


def _body_blocks(text):
    """Split a homily's text into paragraph blocks (and mark bullet lines)."""
    if not text:
        return []
    t = (text.replace(" ", "\n").replace(" ", "\n\n")
             .replace("\r\n", "\n").replace("\r", "\n"))
    blocks = []
    for raw in re.split(r"\n+", t):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^\s*(?:[•‣●·*]|[-–])\s+(.*)", line)
        if m:
            blocks.append(("bullet", m.group(1)))
        else:
            blocks.append(("para", line))
    return blocks


def build_docx(title, homilies):
    """homilies: list of dicts with keys title, type, liturgical_day, season,
    cycle_year, status, readings (role->citation), tags (list), body, and an
    optional person line. Returns a BytesIO of the .docx."""
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = "Georgia"
    normal.font.size = Pt(11)

    # Cover
    h = doc.add_heading(title, level=0)
    sub = doc.add_paragraph(f"{len(homilies)} homil"
                            f"{'y' if len(homilies) == 1 else 'ies'}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    for i, hom in enumerate(homilies):
        doc.add_heading(hom.get("title") or "Untitled", level=1)

        meta_bits = []
        if hom.get("type"):
            meta_bits.append(hom["type"].capitalize())
        if hom.get("liturgical_day"):
            meta_bits.append(hom["liturgical_day"])
        if hom.get("cycle_year"):
            meta_bits.append("Year " + hom["cycle_year"])
        if hom.get("season"):
            meta_bits.append(hom["season"].replace("_", " "))
        if hom.get("status"):
            meta_bits.append(hom["status"])
        if meta_bits:
            p = doc.add_paragraph()
            run = p.add_run("  ·  ".join(meta_bits))
            run.italic = True
            run.font.color.rgb = RGBColor(0x6b, 0x66, 0x5d)

        if hom.get("person"):
            doc.add_paragraph(hom["person"])

        readings = hom.get("readings") or {}
        if any(readings.values()):
            p = doc.add_paragraph()
            parts = [f"{READING_LABELS[r]}: {readings[r]}"
                     for r in READING_ORDER if readings.get(r)]
            run = p.add_run("   ".join(parts))
            run.font.size = Pt(10)

        for kind, content in _body_blocks(hom.get("body")):
            if kind == "bullet":
                doc.add_paragraph(content, style="List Bullet")
            else:
                doc.add_paragraph(content)

        if hom.get("tags"):
            p = doc.add_paragraph()
            run = p.add_run("Tags: " + ", ".join(hom["tags"]))
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x6b, 0x66, 0x5d)

        if i != len(homilies) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

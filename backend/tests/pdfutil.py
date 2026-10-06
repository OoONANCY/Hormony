"""Build small but real PDF files for tests (text pages, or blank 'scanned' pages)."""
from __future__ import annotations

import io
from typing import List


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: List[List[str]]) -> bytes:
    """One page per list of lines; an empty list makes a page with no text layer (like a scan)."""
    objects = {1: "<< /Type /Catalog /Pages 2 0 R >>", 3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids, n = [], 3
    for lines in pages:
        page_id, content_id = n + 1, n + 2
        n += 2
        stream = "".join(f"BT /F1 11 Tf 72 {760 - 16 * i} Td ({_esc(line)}) Tj ET\n" for i, line in enumerate(lines))
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        objects[content_id] = f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}endstream"
        kids.append(page_id)
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for i in sorted(objects):
        offsets[i] = len(out)
        out += f"{i} 0 obj\n{objects[i]}\nendobj\n".encode("latin-1")
    xref, size = len(out), max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for i in range(1, size):
        out += f"{offsets[i]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_png(width: int = 600, height: int = 400) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(img).text((20, 20), "Progesterone 4.8 ng/mL", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


LAB_REPORT = [
    "City Diagnostics Laboratory",
    "Patient: Test Person",
    "Collection date: 2026-10-02",
    "Test Result Units Reference range",
    "Progesterone 4.8 ng/mL 1.8-23.9",
    "Estradiol 156 pg/mL 27-433",
    "TSH 2.1 mIU/L 0.4-4.0",
    "Ferritin 14 ng/mL 15-150 L",
    "Vitamin B12 380 pg/mL 200-900",
]

"""PDF text extraction, scanned-page detection, and image preparation for the vision model."""
from __future__ import annotations

import io
from typing import List, Tuple

MAX_VISION_PAGES = 4
MAX_SIDE = 1800                 # px; keeps phone photos well under provider upload limits
MIN_TEXT_CHARS = 80             # less text than this on every page means it's a scan


def page_texts(data: bytes) -> List[str]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def has_text_layer(texts: List[str]) -> bool:
    return sum(len(t) for t in texts) >= MIN_TEXT_CHARS


def _jpeg(img) -> bytes:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def render_pages(data: bytes) -> List[Tuple[str, bytes]]:
    """Scanned PDF -> up to MAX_VISION_PAGES JPEG page images."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    try:
        return [("image/jpeg", _jpeg(pdf[i].render(scale=2).to_pil())) for i in range(min(len(pdf), MAX_VISION_PAGES))]
    finally:
        pdf.close()


def prepare_image(data: bytes) -> Tuple[str, bytes]:
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))   # phone photos carry their rotation in EXIF
    return "image/jpeg", _jpeg(img)

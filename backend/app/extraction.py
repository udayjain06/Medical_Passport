from __future__ import annotations

import io

import numpy as np
import pypdfium2 as pdfium
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

_engine: RapidOCR | None = None


def _ocr_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def extract_pages(data: bytes, file_format: str) -> list[dict]:
    if file_format == "pdf":
        pdf = pdfium.PdfDocument(data)
        if len(pdf) > 20:
            raise ValueError("Documents over 20 pages need to be split before processing")
        images = [page.render(scale=1.5).to_pil().convert("RGB") for page in pdf]
    elif file_format in {"jpg", "png"}:
        images = [Image.open(io.BytesIO(data)).convert("RGB")]
    else:
        raise ValueError("Unsupported document format")
    output = []
    engine = _ocr_engine()
    for page_number, image in enumerate(images, start=1):
        result, _elapsed = engine(np.asarray(image))
        lines = []
        if result:
            for _box, text, confidence in result:
                if str(text).strip():
                    lines.append({"text": str(text).strip(), "confidence": float(confidence)})
        output.append({"page": page_number, "lines": lines})
    return output

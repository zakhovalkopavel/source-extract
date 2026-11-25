"""Region OCR over page-ocr with own-OCR fallback stub."""

from __future__ import annotations

import io
from typing import Any

from source_extract.models.ocr.ocr_candidate import OcrCandidate


class OcrRegionRunner:
    """``ocr_region(image, box, …)`` → candidates."""

    def ocr_region(
        self,
        image: Any,
        box: tuple[int, int, int, int],
        *,
        engine: str = "page-ocr",
        prompt: str | None = None,
        language: str = "eng",
        whitelist: str | None = None,
        psm: int | None = None,
        scale: float = 1.0,
        rotate: float = 0.0,
    ) -> list[OcrCandidate]:
        params = {
            "engine": engine,
            "prompt": prompt,
            "language": language,
            "whitelist": whitelist,
            "psm": psm,
            "scale": scale,
            "rotate": rotate,
        }
        crop = self._crop(image, box, scale=scale)
        candidates: list[OcrCandidate] = []
        if engine in {"page-ocr", "surya", "vlm"}:
            candidates.extend(self._via_page_ocr(crop, box, params))
        if not candidates or engine in {"own", "tesseract", "fallback"}:
            candidates.extend(self._own_ocr_fallback(crop, box, params))
        return candidates

    def _via_page_ocr(
        self,
        crop: Any,
        box: tuple[int, int, int, int],
        params: dict[str, Any],
    ) -> list[OcrCandidate]:
        try:
            from page_ocr import ocr_page  # type: ignore[import-untyped]
        except ImportError:
            return []
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        result = ocr_page(buf.getvalue())
        text = ""
        if isinstance(result, dict):
            blocks = result.get("blocks") or result.get("text_lines") or []
            if isinstance(blocks, list):
                text = " ".join(
                    (b.get("text") if isinstance(b, dict) else str(b)) for b in blocks
                ).strip()
            else:
                text = str(result.get("text") or "")
        else:
            text = str(result)
        if not text:
            return []
        return [
            OcrCandidate(
                text=text,
                confidence=0.7,
                engine="page-ocr",
                box=box,
                parameters=params,
            )
        ]

    def _own_ocr_fallback(
        self,
        crop: Any,
        box: tuple[int, int, int, int],
        params: dict[str, Any],
    ) -> list[OcrCandidate]:
        try:
            import pytesseract  # type: ignore[import-untyped]
        except ImportError:
            return [
                OcrCandidate(
                    text="",
                    confidence=0.0,
                    engine="own-stub",
                    box=box,
                    parameters={**params, "note": "pytesseract unavailable"},
                )
            ]
        config = ""
        if params.get("psm") is not None:
            config += f"--psm {params['psm']} "
        if params.get("whitelist"):
            config += f"-c tessedit_char_whitelist={params['whitelist']}"
        text = pytesseract.image_to_string(crop, lang=params.get("language") or "eng", config=config).strip()
        return [
            OcrCandidate(
                text=text,
                confidence=0.5 if text else 0.0,
                engine="tesseract",
                box=box,
                parameters=params,
            )
        ]

    @staticmethod
    def _crop(image: Any, box: tuple[int, int, int, int], *, scale: float) -> Any:
        from PIL import Image

        if isinstance(image, (bytes, bytearray)):
            img = Image.open(io.BytesIO(image)).convert("RGB")
        elif isinstance(image, Image.Image):
            img = image
        else:
            img = Image.open(image).convert("RGB")
        x0, y0, x1, y1 = box
        crop = img.crop((x0, y0, x1, y1))
        if scale and scale != 1.0:
            w, h = crop.size
            crop = crop.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        return crop

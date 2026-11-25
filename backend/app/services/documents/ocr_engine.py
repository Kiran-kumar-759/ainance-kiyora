import io
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
import pymupdf
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrLineItem:
    text: str
    confidence: float
    bbox: list[list[float]] = field(default_factory=list)


@dataclass
class OcrPageOutput:
    page_number: int
    text: str
    lines: list[OcrLineItem]
    used_ocr: bool
    average_confidence: float


@dataclass
class OcrDocumentOutput:
    engine_name: str
    engine_version: str
    full_text: str
    pages: list[OcrPageOutput]
    total_pages: int
    processed_pages: int
    warnings: list[str]
    average_confidence: float


class OcrProvider(ABC):
    """Provider-independent interface for local or pluggable OCR engines."""

    engine_name: str = "abstract"
    engine_version: str = "1.0"

    @abstractmethod
    def recognize_image_array(self, image_bgr: np.ndarray) -> list[OcrLineItem]:
        """Runs OCR on a preprocessed BGR OpenCV image array."""


class RapidOcrProvider(OcrProvider):
    """
    Local CPU OCR provider executing official PaddleOCR PP-OCRv4/PP-OCRv3 models
    via RapidOCR + ONNX Runtime (lazy-loaded singleton, zero paid external APIs).
    """

    engine_name = "rapidocr_paddleocr"
    engine_version = "rapidocr-onnx"

    def __init__(self):
        self._engine: Any = None
        self._lock = threading.Lock()

    def _get_engine(self):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    from rapidocr import RapidOCR

                    self._engine = RapidOCR()
        return self._engine

    def recognize_image_array(self, image_bgr: np.ndarray) -> list[OcrLineItem]:
        engine = self._get_engine()
        result = engine(image_bgr)
        items: list[OcrLineItem] = []

        # RapidOCR v3 returns RapidOCROutput with .boxes, .txts, .scores
        txts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)
        if txts:
            for idx, txt in enumerate(txts):
                if not txt or not str(txt).strip():
                    continue
                conf = float(scores[idx]) if scores is not None and idx < len(scores) else 0.75
                bbox: list[list[float]] = []
                if boxes is not None and idx < len(boxes):
                    try:
                        bbox = [[float(x), float(y)] for x, y in boxes[idx]]
                    except Exception:
                        bbox = []
                items.append(OcrLineItem(text=str(txt).strip(), confidence=conf, bbox=bbox))
            return items

        # Legacy tuple fallback: list of [box, text, score]
        if isinstance(result, tuple) and result[0]:
            for row in result[0]:
                if len(row) >= 3 and row[1]:
                    items.append(
                        OcrLineItem(
                            text=str(row[1]).strip(),
                            confidence=float(row[2]),
                            bbox=[],
                        )
                    )
        return items


class PaddleOcrNativeProvider(OcrProvider):
    """Optional native PaddleOCR adapter when paddlepaddle is available in environment."""

    engine_name = "paddleocr"
    engine_version = "native"

    def __init__(self):
        self._engine: Any = None
        self._lock = threading.Lock()

    def _get_engine(self):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    from paddleocr import PaddleOCR

                    self._engine = PaddleOCR(
                        use_angle_cls=settings.OCR_USE_ANGLE_CLS,
                        lang="en",
                        use_gpu=False,
                        show_log=False,
                    )
        return self._engine

    def recognize_image_array(self, image_bgr: np.ndarray) -> list[OcrLineItem]:
        engine = self._get_engine()
        res = engine.ocr(image_bgr, cls=settings.OCR_USE_ANGLE_CLS)
        items: list[OcrLineItem] = []
        for page in res or []:
            for entry in page or []:
                if len(entry) >= 2 and entry[1]:
                    txt, conf = entry[1]
                    if txt and str(txt).strip():
                        items.append(
                            OcrLineItem(text=str(txt).strip(), confidence=float(conf), bbox=[])
                        )
        return items


_PROVIDER_LOCK = threading.Lock()
_CACHED_PROVIDER: OcrProvider | None = None


def get_ocr_provider() -> OcrProvider:
    """Returns lazily initialized singleton OCR provider configured by OCR_ENGINE."""
    global _CACHED_PROVIDER
    if _CACHED_PROVIDER is not None:
        return _CACHED_PROVIDER
    with _PROVIDER_LOCK:
        if _CACHED_PROVIDER is None:
            pref = (settings.OCR_ENGINE or "rapidocr").lower()
            if pref == "paddleocr":
                try:
                    import paddle  # noqa: F401
                    import paddleocr  # noqa: F401

                    _CACHED_PROVIDER = PaddleOcrNativeProvider()
                    return _CACHED_PROVIDER
                except Exception:
                    logger.info("Native paddleocr/paddlepaddle unavailable; using RapidOCR ONNX.")
            _CACHED_PROVIDER = RapidOcrProvider()
        return _CACHED_PROVIDER


def preprocess_image_for_ocr(image_bgr: np.ndarray) -> np.ndarray:
    """
    Applies OpenCV preprocessing suited for printed & phone-captured Indian bills:
    - Upscale small images so thin digits (GSTIN / decimal totals) remain crisp
    - CLAHE luminance contrast enhancement
    - Mild bilateral/Gaussian denoising preserving sharp glyph edges
    """
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Empty image buffer passed to OCR preprocessor.")

    h, w = image_bgr.shape[:2]
    max_dim = max(h, w)
    if max_dim < 900:
        scale = min(2.0, 1200.0 / max(1, max_dim))
        image_bgr = cv2.resize(
            image_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    elif max_dim > 2600:
        scale = 2400.0 / max_dim
        image_bgr = cv2.resize(
            image_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
    enhanced_l = clahe.apply(l_chan)
    merged = cv2.merge((enhanced_l, a_chan, b_chan))
    bgr = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    return cv2.fastNlMeansDenoisingColored(bgr, None, 3, 3, 7, 21)


def _decode_image_bytes_to_bgr(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is not None:
        return bgr
    # Fallback via Pillow (e.g. certain WebP color profiles)
    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)


def render_document_preview_png(data: bytes, file_type: str, page_number: int = 1) -> tuple[bytes, int]:
    """
    Renders a safe PNG preview for PDFs (any 1-based page_number) or images,
    returning (png_bytes, total_pages).
    """
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        with pymupdf.open(stream=data, filetype="pdf") as pdf_doc:
            total = pdf_doc.page_count
            idx = max(0, min(page_number - 1, total - 1))
            page = pdf_doc[idx]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(150 / 72.0, 150 / 72.0), alpha=False)
            return pix.tobytes("png"), total

    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        rgb.thumbnail((1600, 2200))
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue(), 1


def extract_document_text(
    data: bytes,
    file_type: str,
    provider: OcrProvider | None = None,
) -> OcrDocumentOutput:
    """
    Unified page-by-page extraction pipeline:
    - Digital PDF pages with selectable text (>= 30 non-whitespace chars) use PyMuPDF directly.
    - Image documents and scanned PDF pages run OpenCV preprocessing + local OCR provider.
    """
    ocr = provider or get_ocr_provider()
    ext = file_type.lower().lstrip(".")
    warnings: list[str] = []
    pages_out: list[OcrPageOutput] = []

    if ext == "pdf":
        with pymupdf.open(stream=data, filetype="pdf") as pdf_doc:
            total_pages = pdf_doc.page_count
            max_pages = settings.DOCUMENT_MAX_PDF_PAGES
            pages_to_process = min(total_pages, max_pages)
            if total_pages > max_pages:
                warnings.append(
                    f"PDF has {total_pages} pages; processed first {max_pages} pages per resource limit."
                )

            used_native_any = False
            used_ocr_any = False
            for idx in range(pages_to_process):
                page = pdf_doc[idx]
                native_text = (page.get_text("text") or "").strip()
                non_ws_len = len("".join(native_text.split()))
                if non_ws_len >= 30:
                    used_native_any = True
                    raw_lines = [ln.strip() for ln in native_text.splitlines() if ln.strip()]
                    lines = [OcrLineItem(text=ln, confidence=0.98) for ln in raw_lines]
                    pages_out.append(
                        OcrPageOutput(
                            page_number=idx + 1,
                            text="\n".join(raw_lines),
                            lines=lines,
                            used_ocr=False,
                            average_confidence=0.98,
                        )
                    )
                else:
                    used_ocr_any = True
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(200 / 72.0, 200 / 72.0), alpha=False)
                    bgr = _decode_image_bytes_to_bgr(pix.tobytes("png"))
                    pre = preprocess_image_for_ocr(bgr)
                    lines = ocr.recognize_image_array(pre)
                    text_joined = "\n".join(ln.text for ln in lines)
                    avg_c = (
                        sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0
                    )
                    pages_out.append(
                        OcrPageOutput(
                            page_number=idx + 1,
                            text=text_joined,
                            lines=lines,
                            used_ocr=True,
                            average_confidence=round(avg_c, 4),
                        )
                    )

        if used_native_any and not used_ocr_any:
            engine_name = "pymupdf_text"
            engine_version = getattr(pymupdf, "__version__", "pymupdf")
        elif used_native_any and used_ocr_any:
            engine_name = f"hybrid_pymupdf+{ocr.engine_name}"
            engine_version = ocr.engine_version
        else:
            engine_name = ocr.engine_name
            engine_version = ocr.engine_version
    else:
        bgr = _decode_image_bytes_to_bgr(data)
        pre = preprocess_image_for_ocr(bgr)
        lines = ocr.recognize_image_array(pre)
        text_joined = "\n".join(ln.text for ln in lines)
        avg_c = sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0
        pages_out.append(
            OcrPageOutput(
                page_number=1,
                text=text_joined,
                lines=lines,
                used_ocr=True,
                average_confidence=round(avg_c, 4),
            )
        )
        total_pages = 1
        pages_to_process = 1
        engine_name = ocr.engine_name
        engine_version = ocr.engine_version

    full_text = "\n\n".join(
        f"--- Page {p.page_number} ---\n{p.text}" if len(pages_out) > 1 else p.text
        for p in pages_out
        if p.text
    ).strip()

    all_confs = [p.average_confidence for p in pages_out if p.lines]
    overall_avg = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0

    if not full_text:
        warnings.append("No readable text could be extracted from the document.")

    return OcrDocumentOutput(
        engine_name=engine_name,
        engine_version=engine_version,
        full_text=full_text,
        pages=pages_out,
        total_pages=total_pages,
        processed_pages=pages_to_process,
        warnings=warnings,
        average_confidence=overall_avg,
    )

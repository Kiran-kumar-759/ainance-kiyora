import hashlib
import io
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image

from app.core.config import settings

ALLOWED_DOCUMENT_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

DOCUMENT_CATEGORIES: set[str] = {
    "electricity_bill",
    "water_bill",
    "gas_bill",
    "internet_bill",
    "mobile_bill",
    "credit_card_statement",
    "bank_statement",
    "shopping_receipt",
    "travel_receipt",
    "medical_receipt",
    "insurance",
    "tax",
    "loan",
    "subscription_invoice",
    "other",
}


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "document"
    name = os.path.basename(filename).strip()
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name)
    name = name.lstrip(".")
    return name[:240] or "document"


@dataclass
class ValidatedDocument:
    safe_filename: str
    file_type: str
    content_type: str
    file_size: int
    file_hash: str
    page_count: int


def validate_uploaded_document(
    filename: str | None,
    data: bytes,
    max_size_bytes: int | None = None,
) -> ValidatedDocument:
    """
    Strictly validates extension, magic-byte file signature, file size,
    PDF/image structural integrity, and computes SHA-256 hash.
    Never trusts client-supplied MIME types or un-sanitized filenames.
    """
    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Supported documents: .pdf, .png, .jpg, .jpeg, .webp"
        )
    if not data:
        raise ValueError("Uploaded document is empty.")
    cap = max_size_bytes or settings.DOCUMENT_MAX_FILE_SIZE_BYTES
    if len(data) > cap:
        raise ValueError(f"Document exceeds maximum allowed size of {cap // (1024 * 1024)} MB.")

    # Verify magic bytes and parse structural integrity
    page_count = 1
    if ext == ".pdf":
        if not data.lstrip().startswith(b"%PDF"):
            raise ValueError("Invalid PDF signature (file does not match .pdf extension).")
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf_doc:
                if pdf_doc.page_count < 1:
                    raise ValueError("PDF document contains no pages.")
                page_count = pdf_doc.page_count
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Malformed or corrupted PDF file: {exc}") from exc
    elif ext == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG image signature.")
        _verify_image_bytes(data, "PNG")
    elif ext in {".jpg", ".jpeg"}:
        if not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("Invalid JPEG image signature.")
        _verify_image_bytes(data, "JPEG")
    elif ext == ".webp":
        if not (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
            raise ValueError("Invalid WebP image signature.")
        _verify_image_bytes(data, "WEBP")

    file_hash = hashlib.sha256(data).hexdigest()
    return ValidatedDocument(
        safe_filename=safe_name,
        file_type=ext.lstrip("."),
        content_type=ALLOWED_DOCUMENT_EXTENSIONS[ext],
        file_size=len(data),
        file_hash=file_hash,
        page_count=page_count,
    )


def _verify_image_bytes(data: bytes, expected_format: str) -> None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            if img.format and img.format.upper() != expected_format:
                if not (expected_format == "JPEG" and img.format.upper() == "MPO"):
                    raise ValueError(f"Image payload format mismatch ({img.format}).")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Malformed or unreadable {expected_format} image: {exc}") from exc


class PrivateDocumentStorage:
    """
    Private filesystem storage under DOCUMENT_STORAGE_DIR using opaque UUID storage keys.
    Original uploaded bytes are stored untouched and separated from derived OCR artifacts.
    """

    def __init__(self, base_dir: str | Path | None = None):
        raw_dir = Path(base_dir or settings.DOCUMENT_STORAGE_DIR)
        if not raw_dir.is_absolute():
            backend_root = Path(__file__).resolve().parents[3]
            raw_dir = backend_root / raw_dir
        self.base_dir = raw_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        if not storage_key or storage_key.startswith("/") or ".." in Path(storage_key).parts:
            raise ValueError("Invalid storage key.")
        candidate = (self.base_dir / storage_key).resolve()
        if not candidate.is_relative_to(self.base_dir):
            raise ValueError("Path traversal blocked.")
        return candidate

    def save(self, user_id: uuid.UUID, file_ext: str, data: bytes) -> str:
        clean_ext = file_ext.lstrip(".").lower()
        rel_path = Path(str(user_id)) / f"{uuid.uuid4().hex}.{clean_ext}"
        target = self._resolve_safe_path(str(rel_path))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(rel_path)

    def read_bytes(self, storage_key: str) -> bytes:
        target = self._resolve_safe_path(storage_key)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError("Stored document payload not found.")
        return target.read_bytes()

    def delete(self, storage_key: str) -> bool:
        target = self._resolve_safe_path(storage_key)
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False

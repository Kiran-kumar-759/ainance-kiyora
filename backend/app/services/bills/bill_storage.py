import hashlib
import os
import re
import uuid
from pathlib import Path

from app.core.config import settings

ALLOWED_BILL_DOC_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def sanitize_doc_filename(filename: str | None) -> str:
    if not filename:
        return "document"
    name = os.path.basename(filename).strip()
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name)
    return name[:250] or "document"


def validate_bill_document(
    filename: str | None, data: bytes, max_size_bytes: int | None = None
) -> tuple[str, str, str, str]:
    """
    Validates uploaded bill attachment safely:
    Returns (safe_filename, file_type_ext, content_type, sha256_hash).
    """
    safe_name = sanitize_doc_filename(filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_BILL_DOC_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed supporting documents: .pdf, .png, .jpg, .jpeg, .csv, .xlsx"
        )
    if not data:
        raise ValueError("Uploaded document is empty.")
    cap = max_size_bytes or settings.BILL_MAX_DOC_SIZE_BYTES
    if len(data) > cap:
        raise ValueError(f"Document exceeds maximum allowed size of {cap // (1024 * 1024)} MB.")

    # Basic magic-byte check to reject obvious spoofed extensions
    if ext == ".pdf" and not data.lstrip().startswith(b"%PDF"):
        raise ValueError("Invalid PDF document signature.")
    if ext == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG image signature.")
    if ext in {".jpg", ".jpeg"} and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("Invalid JPEG image signature.")
    if ext == ".xlsx" and not data.startswith(b"PK\x03\x04"):
        raise ValueError("Invalid XLSX archive signature.")
    if ext == ".csv" and b"\x00" in data[:4096]:
        raise ValueError("Invalid binary bytes detected in CSV document.")

    file_hash = hashlib.sha256(data).hexdigest()
    return safe_name, ext.lstrip("."), ALLOWED_BILL_DOC_EXTENSIONS[ext], file_hash


class BillDocumentStorage:
    """Private filesystem storage for bill attachments under BILL_STORAGE_DIR."""

    def __init__(self, base_dir: str | Path | None = None):
        raw_dir = Path(base_dir or settings.BILL_STORAGE_DIR)
        if not raw_dir.is_absolute():
            backend_root = Path(__file__).resolve().parents[3]
            raw_dir = backend_root / raw_dir
        self.base_dir = raw_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        if not storage_key or ".." in Path(storage_key).parts:
            raise ValueError("Invalid storage key.")
        candidate = (self.base_dir / storage_key).resolve()
        if not candidate.is_relative_to(self.base_dir):
            raise ValueError("Path traversal blocked.")
        return candidate

    def save(self, user_id: uuid.UUID, bill_id: uuid.UUID, file_ext: str, data: bytes) -> str:
        clean_ext = file_ext.lstrip(".").lower()
        rel_path = Path(str(user_id)) / str(bill_id) / f"{uuid.uuid4().hex}.{clean_ext}"
        target = self._resolve_safe_path(str(rel_path))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(rel_path)

    def read_bytes(self, storage_key: str) -> bytes:
        target = self._resolve_safe_path(storage_key)
        if not target.exists():
            raise FileNotFoundError("Stored bill document not found.")
        return target.read_bytes()

    def delete(self, storage_key: str) -> bool:
        target = self._resolve_safe_path(storage_key)
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False

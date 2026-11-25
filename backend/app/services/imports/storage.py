import datetime as dt
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class ImportStorageBackend(ABC):
    """Abstract private file storage backend for uploaded statements."""

    @abstractmethod
    def save(self, user_id: uuid.UUID, batch_id: uuid.UUID, file_ext: str, data: bytes) -> str:
        """Persists raw uploaded bytes privately and returns an opaque storage_key."""

    @abstractmethod
    def read_bytes(self, storage_key: str) -> bytes:
        """Reads raw uploaded bytes by storage_key."""

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """Deletes the stored file if present."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Checks whether the stored file exists."""


class LocalPrivateFileStorage(ImportStorageBackend):
    """
    Local private filesystem storage scoped inside IMPORT_STORAGE_DIR.
    Uses generated UUID keys only—never trusts user filenames—and blocks path traversal.
    """

    def __init__(self, base_dir: str | Path | None = None):
        raw_dir = Path(base_dir or settings.IMPORT_STORAGE_DIR)
        if not raw_dir.is_absolute():
            # Anchor relative paths to backend workspace directory
            backend_root = Path(__file__).resolve().parents[3]
            raw_dir = backend_root / raw_dir
        self.base_dir = raw_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        if not storage_key or ".." in Path(storage_key).parts:
            raise ValueError("Invalid storage key.")
        candidate = (self.base_dir / storage_key).resolve()
        if not candidate.is_relative_to(self.base_dir):
            raise ValueError("Path traversal attempt blocked.")
        return candidate

    def save(self, user_id: uuid.UUID, batch_id: uuid.UUID, file_ext: str, data: bytes) -> str:
        clean_ext = file_ext.lstrip(".").lower()
        if clean_ext not in {"csv", "xlsx"}:
            raise ValueError(f"Unsupported storage extension: {clean_ext}")
        rel_path = Path(str(user_id)) / str(batch_id) / f"{uuid.uuid4().hex}.{clean_ext}"
        target = self._resolve_safe_path(str(rel_path))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(rel_path)

    def read_bytes(self, storage_key: str) -> bytes:
        target = self._resolve_safe_path(storage_key)
        if not target.exists():
            raise FileNotFoundError(f"Stored import file not found: {storage_key}")
        return target.read_bytes()

    def delete(self, storage_key: str) -> bool:
        target = self._resolve_safe_path(storage_key)
        if target.exists() and target.is_file():
            target.unlink()
            # Clean up empty batch directory if empty
            try:
                if target.parent != self.base_dir and not any(target.parent.iterdir()):
                    target.parent.rmdir()
            except OSError:
                pass
            return True
        return False

    def exists(self, storage_key: str) -> bool:
        try:
            target = self._resolve_safe_path(storage_key)
            return target.exists() and target.is_file()
        except ValueError:
            return False

    def cleanup_expired_files(self, retention_days: int | None = None) -> int:
        """Removes stored files older than retention_days."""
        days = retention_days if retention_days is not None else settings.IMPORT_FILE_RETENTION_DAYS
        cutoff = dt.datetime.now(dt.UTC).timestamp() - (days * 86400)
        removed = 0
        for path in self.base_dir.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

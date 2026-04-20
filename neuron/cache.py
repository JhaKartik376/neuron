"""SHA256-based incremental extraction cache — only re-process changed files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ExtractionCache:
    """Persistent cache mapping file hashes to extraction results.

    Stores cached extractions in a JSON file. On re-run, only files whose
    SHA256 hash has changed are re-extracted.
    """

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "extraction_cache.json"
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.cache_file.is_file():
            try:
                self._data = json.loads(self.cache_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self):
        self.cache_file.write_text(json.dumps(self._data, indent=2, default=str))

    @staticmethod
    def file_hash(path: Path) -> str:
        """Compute SHA256 hash of file contents."""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()[:16]

    def get(self, filepath: str, file_hash: str) -> dict[str, Any] | None:
        """Get cached extraction result if hash matches."""
        entry = self._data.get(filepath)
        if entry and entry.get("hash") == file_hash:
            return entry.get("result")
        return None

    def put(self, filepath: str, file_hash: str, result: dict[str, Any]):
        """Store extraction result in cache."""
        self._data[filepath] = {
            "hash": file_hash,
            "result": result,
        }

    def invalidate(self, filepath: str):
        """Remove a file from cache."""
        self._data.pop(filepath, None)

    def save(self):
        """Persist cache to disk."""
        self._save()

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        return {
            "entries": len(self._data),
            "size_bytes": self.cache_file.stat().st_size if self.cache_file.is_file() else 0,
        }

    def clear(self):
        """Clear all cached entries."""
        self._data = {}
        self._save()

"""File discovery, classification, and manifest detection."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FileKind(str, Enum):
    CODE = "code"
    DOCUMENT = "document"
    CONFIG = "config"
    DATA = "data"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    MANIFEST = "manifest"  # package.json, Cargo.toml, go.mod, etc.
    UNKNOWN = "unknown"


# Extension → (kind, language/format)
_EXT_MAP: dict[str, tuple[FileKind, str]] = {
    # Code
    ".py": (FileKind.CODE, "python"),
    ".js": (FileKind.CODE, "javascript"),
    ".jsx": (FileKind.CODE, "javascript"),
    ".ts": (FileKind.CODE, "typescript"),
    ".tsx": (FileKind.CODE, "typescript"),
    ".go": (FileKind.CODE, "go"),
    ".rs": (FileKind.CODE, "rust"),
    ".java": (FileKind.CODE, "java"),
    ".c": (FileKind.CODE, "c"),
    ".h": (FileKind.CODE, "c"),
    ".cpp": (FileKind.CODE, "cpp"),
    ".hpp": (FileKind.CODE, "cpp"),
    ".cc": (FileKind.CODE, "cpp"),
    ".rb": (FileKind.CODE, "ruby"),
    ".cs": (FileKind.CODE, "c_sharp"),
    ".kt": (FileKind.CODE, "kotlin"),
    ".scala": (FileKind.CODE, "scala"),
    ".php": (FileKind.CODE, "php"),
    ".swift": (FileKind.CODE, "swift"),
    ".lua": (FileKind.CODE, "lua"),
    ".zig": (FileKind.CODE, "zig"),
    ".ex": (FileKind.CODE, "elixir"),
    ".exs": (FileKind.CODE, "elixir"),
    ".jl": (FileKind.CODE, "julia"),
    ".sh": (FileKind.CODE, "bash"),
    ".bash": (FileKind.CODE, "bash"),
    ".zsh": (FileKind.CODE, "bash"),
    ".pl": (FileKind.CODE, "perl"),
    ".r": (FileKind.CODE, "r"),
    ".R": (FileKind.CODE, "r"),
    ".dart": (FileKind.CODE, "dart"),
    ".vue": (FileKind.CODE, "vue"),
    ".svelte": (FileKind.CODE, "svelte"),
    # Documents
    ".md": (FileKind.DOCUMENT, "markdown"),
    ".mdx": (FileKind.DOCUMENT, "markdown"),
    ".txt": (FileKind.DOCUMENT, "text"),
    ".rst": (FileKind.DOCUMENT, "restructuredtext"),
    ".adoc": (FileKind.DOCUMENT, "asciidoc"),
    ".pdf": (FileKind.DOCUMENT, "pdf"),
    ".docx": (FileKind.DOCUMENT, "docx"),
    ".tex": (FileKind.DOCUMENT, "latex"),
    # Config
    ".json": (FileKind.CONFIG, "json"),
    ".yaml": (FileKind.CONFIG, "yaml"),
    ".yml": (FileKind.CONFIG, "yaml"),
    ".toml": (FileKind.CONFIG, "toml"),
    ".ini": (FileKind.CONFIG, "ini"),
    ".cfg": (FileKind.CONFIG, "ini"),
    ".xml": (FileKind.CONFIG, "xml"),
    ".env": (FileKind.CONFIG, "env"),
    # Data
    ".csv": (FileKind.DATA, "csv"),
    ".tsv": (FileKind.DATA, "tsv"),
    ".parquet": (FileKind.DATA, "parquet"),
    ".sql": (FileKind.DATA, "sql"),
    # Images
    ".png": (FileKind.IMAGE, "png"),
    ".jpg": (FileKind.IMAGE, "jpeg"),
    ".jpeg": (FileKind.IMAGE, "jpeg"),
    ".gif": (FileKind.IMAGE, "gif"),
    ".svg": (FileKind.IMAGE, "svg"),
    ".webp": (FileKind.IMAGE, "webp"),
    # Video/Audio
    ".mp4": (FileKind.VIDEO, "mp4"),
    ".webm": (FileKind.VIDEO, "webm"),
    ".mov": (FileKind.VIDEO, "mov"),
    ".avi": (FileKind.VIDEO, "avi"),
    ".mp3": (FileKind.AUDIO, "mp3"),
    ".wav": (FileKind.AUDIO, "wav"),
    ".flac": (FileKind.AUDIO, "flac"),
}

# Filename → manifest kind
_MANIFEST_FILES: dict[str, str] = {
    "package.json": "npm",
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "Cargo.toml": "cargo",
    "Cargo.lock": "cargo",
    "go.mod": "go",
    "go.sum": "go",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "pip",
    "Pipfile": "pipenv",
    "Pipfile.lock": "pipenv",
    "poetry.lock": "poetry",
    "Gemfile": "bundler",
    "Gemfile.lock": "bundler",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "composer.json": "composer",
    "mix.exs": "mix",
    "pubspec.yaml": "pub",
    "Package.swift": "swift-pm",
    "*.csproj": "nuget",
    "*.sln": "dotnet",
}

# Directories to always skip
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    ".tox",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".neuron-out",
})

# Sensitive file patterns to skip
_SENSITIVE_PATTERNS: list[str] = [
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "id_rsa*",
    "id_ed25519*",
    ".env*",
    "*credentials*",
    "*secret*",
    "*.secret",
]


@dataclass
class DetectedFile:
    path: Path
    relative: str
    kind: FileKind
    language: str
    size: int
    manifest_type: str | None = None


@dataclass
class DetectionResult:
    root: Path
    files: list[DetectedFile] = field(default_factory=list)
    manifests: list[DetectedFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    total_size: int = 0

    @property
    def code_files(self) -> list[DetectedFile]:
        return [f for f in self.files if f.kind == FileKind.CODE]

    @property
    def document_files(self) -> list[DetectedFile]:
        return [f for f in self.files if f.kind == FileKind.DOCUMENT]

    @property
    def languages(self) -> set[str]:
        return {f.language for f in self.files if f.kind == FileKind.CODE}

    def summary(self) -> dict:
        by_kind: dict[str, int] = {}
        for f in self.files:
            by_kind[f.kind.value] = by_kind.get(f.kind.value, 0) + 1
        return {
            "total_files": len(self.files),
            "total_size": self.total_size,
            "by_kind": by_kind,
            "languages": sorted(self.languages),
            "manifests": len(self.manifests),
            "skipped": len(self.skipped),
        }


def _load_ignore_patterns(root: Path) -> list[str]:
    """Load patterns from .neuronignore file."""
    ignore_file = root / ".neuronignore"
    patterns: list[str] = []
    if ignore_file.is_file():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def _is_sensitive(name: str) -> bool:
    """Check if filename matches a sensitive pattern."""
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pat) for pat in _SENSITIVE_PATTERNS)


def _classify(filepath: Path) -> tuple[FileKind, str, str | None]:
    """Classify a file by extension and name. Returns (kind, language, manifest_type)."""
    name = filepath.name

    # Check manifest first
    for pattern, mtype in _MANIFEST_FILES.items():
        if "*" in pattern:
            if fnmatch.fnmatch(name, pattern):
                return FileKind.MANIFEST, "manifest", mtype
        elif name == pattern:
            return FileKind.MANIFEST, "manifest", mtype

    ext = filepath.suffix.lower()
    if ext in _EXT_MAP:
        kind, lang = _EXT_MAP[ext]
        return kind, lang, None

    return FileKind.UNKNOWN, "unknown", None


def detect(
    root: str | Path,
    max_file_size: int = 5 * 1024 * 1024,  # 5MB
    include_hidden: bool = False,
) -> DetectionResult:
    """Discover and classify all files under root.

    Args:
        root: Directory to scan.
        max_file_size: Skip files larger than this (bytes).
        include_hidden: Whether to include hidden files/dirs.

    Returns:
        DetectionResult with classified files, manifests, and skip info.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    ignore_patterns = _load_ignore_patterns(root)
    result = DetectionResult(root=root)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        rel_dir = os.path.relpath(dirpath, root)

        # Prune directories
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_DIRS
            and (include_hidden or not d.startswith("."))
            and not any(fnmatch.fnmatch(d, p) for p in ignore_patterns)
        ]

        for filename in filenames:
            if not include_hidden and filename.startswith("."):
                continue

            filepath = Path(dirpath) / filename
            relative = os.path.join(rel_dir, filename) if rel_dir != "." else filename

            # Check ignore patterns
            if any(fnmatch.fnmatch(relative, p) or fnmatch.fnmatch(filename, p) for p in ignore_patterns):
                result.skipped.append(relative)
                continue

            # Skip sensitive files
            if _is_sensitive(filename):
                result.skipped.append(relative)
                continue

            try:
                stat = filepath.stat()
            except OSError:
                result.skipped.append(relative)
                continue

            if stat.st_size > max_file_size:
                result.skipped.append(relative)
                continue

            if stat.st_size == 0:
                continue

            kind, language, manifest_type = _classify(filepath)

            if kind == FileKind.UNKNOWN:
                continue

            detected = DetectedFile(
                path=filepath,
                relative=relative,
                kind=kind,
                language=language,
                size=stat.st_size,
                manifest_type=manifest_type,
            )

            if kind == FileKind.MANIFEST:
                result.manifests.append(detected)
            else:
                result.files.append(detected)

            result.total_size += stat.st_size

    # Sort by path for deterministic ordering
    result.files.sort(key=lambda f: f.relative)
    result.manifests.sort(key=lambda f: f.relative)

    return result

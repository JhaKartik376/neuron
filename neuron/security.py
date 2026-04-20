"""Security utilities: input validation, label sanitization, SSRF protection."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_PRIVATE_RANGES = [
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.", "127.", "0.",
    "169.254.", "::1", "fc00:", "fe80:", "fd",
]


def sanitize_label(label: str, max_length: int = 200) -> str:
    """Sanitize a node/edge label for safe rendering."""
    # Strip control characters
    label = re.sub(r"[\x00-\x1f\x7f]", "", label)
    # Escape HTML entities
    label = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    label = label.replace('"', "&quot;").replace("'", "&#39;")
    return label[:max_length]


def validate_url(url: str, allow_private: bool = False) -> bool:
    """Validate a URL is safe to fetch (no SSRF)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.hostname or ""

    if not allow_private:
        if host in ("localhost", ""):
            return False
        for prefix in _PRIVATE_RANGES:
            if host.startswith(prefix):
                return False

    return True


def is_sensitive_file(filename: str) -> bool:
    """Check if a filename likely contains secrets."""
    lower = filename.lower()
    sensitive_names = {
        ".env", ".env.local", ".env.production", ".env.development",
        "credentials.json", "credentials.yaml", "service-account.json",
        "id_rsa", "id_ed25519", "id_ecdsa",
    }
    sensitive_extensions = {
        ".key", ".pem", ".p12", ".pfx", ".keystore", ".jks",
    }

    name = lower.rsplit("/", 1)[-1]
    if name in sensitive_names:
        return True

    for ext in sensitive_extensions:
        if lower.endswith(ext):
            return True

    if "secret" in lower or "password" in lower or "token" in lower:
        if lower.endswith((".json", ".yaml", ".yml", ".env", ".txt")):
            return True

    return False

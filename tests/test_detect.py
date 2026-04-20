"""Tests for file detection and classification."""

from pathlib import Path

from neuron.detect import FileKind, detect, _classify, _is_sensitive


FIXTURES = Path(__file__).parent / "fixtures"


def test_classify_python():
    kind, lang, mtype = _classify(Path("example.py"))
    assert kind == FileKind.CODE
    assert lang == "python"
    assert mtype is None


def test_classify_javascript():
    kind, lang, mtype = _classify(Path("index.js"))
    assert kind == FileKind.CODE
    assert lang == "javascript"


def test_classify_manifest():
    kind, lang, mtype = _classify(Path("package.json"))
    assert kind == FileKind.MANIFEST
    assert mtype == "npm"


def test_classify_cargo():
    kind, lang, mtype = _classify(Path("Cargo.toml"))
    assert kind == FileKind.MANIFEST
    assert mtype == "cargo"


def test_classify_document():
    kind, lang, mtype = _classify(Path("README.md"))
    assert kind == FileKind.DOCUMENT
    assert lang == "markdown"


def test_classify_unknown():
    kind, lang, mtype = _classify(Path("mystery.xyz"))
    assert kind == FileKind.UNKNOWN


def test_sensitive_env():
    assert _is_sensitive(".env") is True
    assert _is_sensitive(".env.local") is True


def test_sensitive_key():
    assert _is_sensitive("server.key") is True
    assert _is_sensitive("cert.pem") is True


def test_not_sensitive():
    assert _is_sensitive("main.py") is False
    assert _is_sensitive("README.md") is False


def test_detect_fixtures():
    result = detect(FIXTURES)
    assert len(result.files) >= 2  # sample.py, sample.js
    assert any(f.language == "python" for f in result.files)
    assert any(f.language == "javascript" for f in result.files)


def test_detect_summary():
    result = detect(FIXTURES)
    summary = result.summary()
    assert summary["total_files"] >= 2
    assert "python" in summary["languages"]

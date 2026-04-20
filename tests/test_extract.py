"""Tests for entity extraction."""

from pathlib import Path

from neuron.detect import DetectedFile, FileKind
from neuron.extract import Confidence, extract_file


FIXTURES = Path(__file__).parent / "fixtures"


def _make_detected(filename: str, kind: FileKind, language: str) -> DetectedFile:
    path = FIXTURES / filename
    return DetectedFile(
        path=path,
        relative=filename,
        kind=kind,
        language=language,
        size=path.stat().st_size,
    )


def test_extract_python():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    assert result.language == "python"
    assert result.file_hash != ""
    assert len(result.entities) > 0
    assert len(result.relations) > 0

    # Should find the module
    names = [e.name for e in result.entities]
    assert "sample" in names

    # Should find classes
    assert "DataProcessor" in names
    assert "FileExporter" in names

    # Should find functions
    assert "run_pipeline" in names
    assert "load_records" in names


def test_extract_python_methods():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    names = [e.name for e in result.entities]
    assert "DataProcessor.process" in names
    assert "DataProcessor._clean" in names
    assert "DataProcessor._validate" in names


def test_extract_python_visibility():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    entities_by_name = {e.name: e for e in result.entities}
    assert entities_by_name["DataProcessor._clean"].visibility == "private"
    assert entities_by_name["run_pipeline"].visibility == "public"


def test_extract_python_relations():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    # Should have import relations
    import_rels = [r for r in result.relations if r.kind == "imports"]
    assert len(import_rels) > 0

    # Should have contains relations
    contains_rels = [r for r in result.relations if r.kind == "contains"]
    assert len(contains_rels) > 0

    # Should have inherits relations (none in this file, but verify no crash)
    # Should have calls relations
    calls_rels = [r for r in result.relations if r.kind == "calls"]
    assert len(calls_rels) > 0


def test_extract_python_docstrings():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    entities_by_name = {e.name: e for e in result.entities}
    assert entities_by_name["DataProcessor"].docstring is not None
    assert "data records" in entities_by_name["DataProcessor"].docstring.lower()


def test_extract_python_confidence():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)

    # All AST-extracted relations should be EXTRACTED confidence
    for rel in result.relations:
        assert rel.confidence == Confidence.EXTRACTED


def test_extract_javascript():
    detected = _make_detected("sample.js", FileKind.CODE, "javascript")
    result = extract_file(detected)

    assert result.language == "javascript"
    names = [e.name for e in result.entities]
    assert "sample" in names  # module name


def test_extract_to_dict():
    detected = _make_detected("sample.py", FileKind.CODE, "python")
    result = extract_file(detected)
    d = result.to_dict()

    assert "file" in d
    assert "entities" in d
    assert "relations" in d
    assert isinstance(d["entities"], list)
    assert len(d["entities"]) > 0

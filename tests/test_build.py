"""Tests for graph building."""

from neuron.build import build_graph, graph_stats, prune_graph
from neuron.extract import Confidence, Entity, ExtractionResult, Relation


def _make_extractions() -> list[ExtractionResult]:
    """Create sample extraction results for testing."""
    ext1 = ExtractionResult(file="module_a.py", file_hash="abc123", language="python")
    ext1.entities = [
        Entity(name="module_a", kind="module", file="module_a.py", line=1),
        Entity(name="ClassA", kind="class", file="module_a.py", line=5),
        Entity(name="func_a", kind="function", file="module_a.py", line=20),
    ]
    ext1.relations = [
        Relation(source="module_a", target="ClassA", kind="contains", file="module_a.py"),
        Relation(source="module_a", target="func_a", kind="contains", file="module_a.py"),
        Relation(source="module_a", target="os", kind="imports", file="module_a.py"),
        Relation(source="func_a", target="ClassA", kind="calls", file="module_a.py"),
    ]

    ext2 = ExtractionResult(file="module_b.py", file_hash="def456", language="python")
    ext2.entities = [
        Entity(name="module_b", kind="module", file="module_b.py", line=1),
        Entity(name="ClassB", kind="class", file="module_b.py", line=3),
    ]
    ext2.relations = [
        Relation(source="module_b", target="ClassB", kind="contains", file="module_b.py"),
        Relation(source="module_b", target="module_a", kind="imports", file="module_b.py"),
        Relation(source="ClassB", target="ClassA", kind="inherits", file="module_b.py"),
    ]

    return [ext1, ext2]


def test_build_basic():
    G = build_graph(_make_extractions())
    assert G.number_of_nodes() > 0
    assert G.number_of_edges() > 0


def test_build_entities_as_nodes():
    G = build_graph(_make_extractions())
    nodes = set(G.nodes())
    assert "module_a" in nodes
    assert "module_b" in nodes
    assert "classa" in nodes
    assert "classb" in nodes
    assert "func_a" in nodes


def test_build_relations_as_edges():
    G = build_graph(_make_extractions())
    assert G.has_edge("module_a", "classa")
    assert G.has_edge("module_b", "module_a")
    assert G.has_edge("classb", "classa")


def test_build_edge_attributes():
    G = build_graph(_make_extractions())
    edge = G["module_a"]["classa"]
    assert "relation" in edge
    assert edge["confidence"] == "extracted"


def test_build_directed():
    G = build_graph(_make_extractions(), directed=True)
    assert G.is_directed()


def test_build_cross_file_resolution():
    G = build_graph(_make_extractions(), resolve_cross_file=True)
    # ClassB inherits ClassA — should be resolved across files
    assert G.has_edge("classb", "classa")


def test_build_external_nodes():
    G = build_graph(_make_extractions())
    # "os" is imported but not defined — should be external
    assert "os" in G.nodes()
    assert G.nodes["os"].get("kind") == "external"


def test_graph_stats():
    G = build_graph(_make_extractions())
    stats = graph_stats(G)
    assert stats["nodes"] > 0
    assert stats["edges"] > 0
    assert "node_kinds" in stats
    assert "edge_relations" in stats


def test_prune_external():
    G = build_graph(_make_extractions())
    H = prune_graph(G, remove_external=True)
    for _, data in H.nodes(data=True):
        assert data.get("kind") != "external"


def test_prune_min_degree():
    G = build_graph(_make_extractions())
    H = prune_graph(G, min_degree=2)
    for node in H.nodes():
        assert H.degree(node) >= 2

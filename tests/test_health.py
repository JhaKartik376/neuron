"""Tests for code health scoring."""

import networkx as nx

from neuron.health import Grade, ModuleHealth, compute_health


def _make_graph() -> nx.Graph:
    """Create a test graph with two modules of different health."""
    G = nx.Graph()

    # Module A: well-structured (high cohesion, low coupling)
    G.add_node("mod_a", label="mod_a", kind="module", file="a.py")
    G.add_node("a_cls", label="ClassA", kind="class", file="a.py")
    G.add_node("a_fn1", label="func1", kind="function", file="a.py")
    G.add_node("a_fn2", label="func2", kind="function", file="a.py")
    G.add_edge("mod_a", "a_cls", relation="contains")
    G.add_edge("mod_a", "a_fn1", relation="contains")
    G.add_edge("mod_a", "a_fn2", relation="contains")
    G.add_edge("a_fn1", "a_fn2", relation="calls")
    G.add_edge("a_cls", "a_fn1", relation="calls")

    # Module B: poorly structured (low cohesion, high coupling)
    G.add_node("mod_b", label="mod_b", kind="module", file="b.py")
    G.add_node("b_fn1", label="b_func1", kind="function", file="b.py")
    G.add_node("b_fn2", label="b_func2", kind="function", file="b.py")
    G.add_edge("mod_b", "b_fn1", relation="contains")
    G.add_edge("mod_b", "b_fn2", relation="contains")
    # High coupling to module A
    G.add_edge("b_fn1", "a_cls", relation="calls")
    G.add_edge("b_fn1", "a_fn1", relation="calls")
    G.add_edge("b_fn1", "a_fn2", relation="calls")
    G.add_edge("b_fn2", "a_cls", relation="calls")
    G.add_edge("b_fn2", "mod_a", relation="imports")

    return G


def test_grade_from_score():
    assert Grade.from_score(0.95) == "A"
    assert Grade.from_score(0.85) == "B"
    assert Grade.from_score(0.75) == "C"
    assert Grade.from_score(0.65) == "D"
    assert Grade.from_score(0.5) == "F"


def test_compute_health_basic():
    G = _make_graph()
    report = compute_health(G)
    assert report.overall_score > 0
    assert report.grade in ("A", "B", "C", "D", "F")
    assert len(report.modules) > 0


def test_health_modules_scored():
    G = _make_graph()
    report = compute_health(G)
    for m in report.modules:
        assert 0 <= m.overall_score <= 1
        assert m.grade in ("A", "B", "C", "D", "F")
        assert 0 <= m.coupling_score <= 1
        assert 0 <= m.cohesion_score <= 1
        assert 0 <= m.complexity_score <= 1


def test_health_recommendations():
    G = _make_graph()
    report = compute_health(G)
    assert len(report.recommendations) > 0


def test_health_to_dict():
    G = _make_graph()
    report = compute_health(G)
    d = report.to_dict()
    assert "overall_score" in d
    assert "grade" in d
    assert "modules" in d
    assert isinstance(d["modules"], list)


def test_empty_graph_health():
    G = nx.Graph()
    report = compute_health(G)
    assert report.overall_score == 0
    assert len(report.modules) == 0

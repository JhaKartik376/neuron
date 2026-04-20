"""Tests for graph diffing."""

import networkx as nx

from neuron.diff import GraphDiff, diff_graphs


def _make_old_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("a", label="A", kind="module", community=0)
    G.add_node("b", label="B", kind="class", community=0)
    G.add_node("c", label="C", kind="function", community=1)
    G.add_edge("a", "b", relation="contains", confidence="extracted")
    G.add_edge("b", "c", relation="calls", confidence="extracted")
    return G


def _make_new_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("a", label="A", kind="module", community=0)
    G.add_node("b", label="B", kind="class", community=0)
    G.add_node("d", label="D", kind="function", community=1)  # new node
    G.add_edge("a", "b", relation="contains", confidence="extracted")
    G.add_edge("a", "d", relation="contains", confidence="extracted")  # new edge
    return G


def test_diff_nodes_added():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    assert result.nodes_added == 1  # D added


def test_diff_nodes_removed():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    assert result.nodes_removed == 1  # C removed


def test_diff_edges_changed():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    assert result.edges_added >= 1  # a→d
    assert result.edges_removed >= 1  # b→c


def test_diff_drift_score():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    assert 0 < result.drift_score < 1


def test_diff_identical():
    G = _make_old_graph()
    result = diff_graphs(G, G)
    assert result.nodes_added == 0
    assert result.nodes_removed == 0
    assert result.drift_score == 0.0


def test_diff_summary():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    summary = result.summary()
    assert isinstance(summary, str)
    assert "drift=" in summary


def test_diff_to_dict():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    d = result.to_dict()
    assert "drift_score" in d
    assert "node_changes" in d
    assert "edge_changes" in d


def test_diff_community_changes():
    result = diff_graphs(_make_old_graph(), _make_new_graph())
    # Communities changed because nodes changed
    assert isinstance(result.community_changes, list)

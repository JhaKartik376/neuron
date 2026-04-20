"""Tests for architecture fitness rules."""

import networkx as nx
import pytest

from neuron.fitness import (
    FitnessRule,
    RuleKind,
    evaluate,
    generate_default_rules,
)


def _make_graph() -> nx.Graph:
    G = nx.Graph()
    G.add_node("ui_comp", label="UIComponent", kind="class", file="ui/component.py")
    G.add_node("ui_view", label="UIView", kind="class", file="ui/view.py")
    G.add_node("svc_user", label="UserService", kind="class", file="services/user.py")
    G.add_node("db_repo", label="UserRepo", kind="class", file="db/repo.py")

    G.add_edge("ui_comp", "svc_user", relation="calls")
    G.add_edge("svc_user", "db_repo", relation="calls")
    # Bad: UI directly accessing DB
    G.add_edge("ui_view", "db_repo", relation="calls")

    return G


def test_no_depend_violation():
    G = _make_graph()
    rules = [FitnessRule(
        name="no-ui-to-db",
        kind=RuleKind.NO_DEPEND,
        source_pattern="ui/*",
        target_pattern="db/*",
        severity="error",
    )]
    report = evaluate(G, rules)
    assert report.failed == 1
    assert len(report.violations) > 0
    assert report.violations[0].severity == "error"


def test_no_depend_passes():
    G = _make_graph()
    # db→ui has no direct edge, so this should pass
    rules = [FitnessRule(
        name="no-db-to-ui",
        kind=RuleKind.NO_DEPEND,
        source_pattern="db/*",
        target_pattern="ui/component*",
        severity="error",
    )]
    report = evaluate(G, rules)
    assert report.passed == 1
    assert len(report.violations) == 0


def test_max_coupling():
    G = _make_graph()
    rules = [FitnessRule(
        name="max-coupling",
        kind=RuleKind.MAX_COUPLING,
        source_pattern="*",
        threshold=1,
        severity="warning",
    )]
    report = evaluate(G, rules)
    # Some nodes have >1 external deps
    assert len(report.violations) > 0


def test_max_fan_out():
    G = _make_graph()
    rules = [FitnessRule(
        name="max-fan-out",
        kind=RuleKind.MAX_FAN_OUT,
        source_pattern="*",
        threshold=1,
        severity="warning",
    )]
    report = evaluate(G, rules)
    assert len(report.violations) > 0


def test_no_circular():
    G = nx.Graph()
    G.add_node("a", label="A", kind="module", file="a.py")
    G.add_node("b", label="B", kind="module", file="b.py")
    G.add_node("c", label="C", kind="module", file="c.py")
    G.add_edge("a", "b", relation="imports")
    G.add_edge("b", "c", relation="imports")
    G.add_edge("c", "a", relation="imports")

    rules = [FitnessRule(
        name="no-circular",
        kind=RuleKind.NO_CIRCULAR,
        source_pattern="*",
        severity="error",
    )]
    report = evaluate(G, rules)
    assert len(report.violations) > 0


def test_generate_default_rules():
    content = generate_default_rules()
    assert "rules:" in content
    assert "max-module-coupling" in content


def test_report_is_healthy():
    G = nx.Graph()
    G.add_node("a", label="A", kind="module", file="a.py")
    rules = [FitnessRule(
        name="trivial",
        kind=RuleKind.MAX_FAN_OUT,
        source_pattern="*",
        threshold=100,
    )]
    report = evaluate(G, rules)
    assert report.is_healthy is True

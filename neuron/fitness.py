"""Architecture fitness rules — define and enforce structural constraints on the graph."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import yaml


class RuleKind:
    NO_DEPEND = "no-depend"          # A must NOT depend on B
    MUST_DEPEND = "must-depend"      # A MUST depend on B
    MAX_COUPLING = "max-coupling"    # Module can have at most N external deps
    MAX_FAN_OUT = "max-fan-out"      # Entity can have at most N outgoing edges
    MAX_FAN_IN = "max-fan-in"        # Entity can have at most N incoming edges
    LAYER_ORDER = "layer-order"      # Enforce layered architecture (A→B ok, B→A not ok)
    NO_CIRCULAR = "no-circular"      # No circular dependencies between matched modules
    MAX_COMMUNITY_SIZE = "max-community-size"  # Community cannot exceed N nodes


@dataclass
class FitnessRule:
    """A single architecture fitness rule."""
    name: str
    kind: str
    description: str = ""
    severity: str = "error"  # error, warning, info
    source_pattern: str = "*"
    target_pattern: str = "*"
    threshold: int | None = None
    layers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> FitnessRule:
        return cls(
            name=d["name"],
            kind=d["kind"],
            description=d.get("description", ""),
            severity=d.get("severity", "error"),
            source_pattern=d.get("source", d.get("source_pattern", "*")),
            target_pattern=d.get("target", d.get("target_pattern", "*")),
            threshold=d.get("threshold"),
            layers=d.get("layers", []),
        )


@dataclass
class Violation:
    """A fitness rule violation."""
    rule: str
    severity: str
    message: str
    source: str | None = None
    target: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FitnessReport:
    """Result of evaluating fitness rules against the graph."""
    rules_checked: int = 0
    violations: list[Violation] = field(default_factory=list)
    passed: int = 0
    failed: int = 0

    @property
    def is_healthy(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "rules_checked": self.rules_checked,
            "passed": self.passed,
            "failed": self.failed,
            "is_healthy": self.is_healthy,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "violations": [
                {
                    "rule": v.rule,
                    "severity": v.severity,
                    "message": v.message,
                    "source": v.source,
                    "target": v.target,
                    "details": v.details,
                }
                for v in self.violations
            ],
        }


def load_rules(path: str | Path) -> list[FitnessRule]:
    """Load fitness rules from a YAML file.

    Example neuron-fitness.yaml:

    ```yaml
    rules:
      - name: no-ui-to-db
        kind: no-depend
        description: UI layer must not directly access database
        source: "ui/*"
        target: "db/*"
        severity: error

      - name: max-controller-coupling
        kind: max-coupling
        source: "controllers/*"
        threshold: 10
        severity: warning

      - name: layered-architecture
        kind: layer-order
        layers:
          - "presentation"
          - "business"
          - "data"
        severity: error

      - name: no-circular-services
        kind: no-circular
        source: "services/*"
        severity: error
    ```
    """
    path = Path(path)
    if not path.is_file():
        return []

    content = path.read_text()
    data = yaml.safe_load(content)

    if not data or "rules" not in data:
        return []

    return [FitnessRule.from_dict(r) for r in data["rules"]]


def _match_nodes(G: nx.Graph, pattern: str) -> list[str]:
    """Find nodes matching a glob/regex pattern against labels and file paths."""
    matched = []
    for node, data in G.nodes(data=True):
        label = data.get("label", node)
        file = data.get("file", "")

        if fnmatch.fnmatch(label, pattern) or fnmatch.fnmatch(file, pattern):
            matched.append(node)
        elif fnmatch.fnmatch(node, pattern):
            matched.append(node)
        else:
            try:
                if re.match(pattern, label) or re.match(pattern, file):
                    matched.append(node)
            except re.error:
                pass

    return matched


def evaluate(G: nx.Graph, rules: list[FitnessRule]) -> FitnessReport:
    """Evaluate all fitness rules against the graph."""
    report = FitnessReport(rules_checked=len(rules))

    for rule in rules:
        violations = _evaluate_rule(G, rule)
        if violations:
            report.violations.extend(violations)
            report.failed += 1
        else:
            report.passed += 1

    return report


def _evaluate_rule(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Evaluate a single fitness rule."""
    dispatch = {
        RuleKind.NO_DEPEND: _check_no_depend,
        RuleKind.MUST_DEPEND: _check_must_depend,
        RuleKind.MAX_COUPLING: _check_max_coupling,
        RuleKind.MAX_FAN_OUT: _check_max_fan_out,
        RuleKind.MAX_FAN_IN: _check_max_fan_in,
        RuleKind.LAYER_ORDER: _check_layer_order,
        RuleKind.NO_CIRCULAR: _check_no_circular,
        RuleKind.MAX_COMMUNITY_SIZE: _check_max_community_size,
    }

    checker = dispatch.get(rule.kind)
    if not checker:
        return [Violation(
            rule=rule.name,
            severity="warning",
            message=f"Unknown rule kind: {rule.kind}",
        )]

    return checker(G, rule)


def _check_no_depend(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Source nodes must NOT have edges to target nodes."""
    violations = []
    sources = _match_nodes(G, rule.source_pattern)
    targets = set(_match_nodes(G, rule.target_pattern))

    for src in sources:
        for neighbor in G.neighbors(src):
            if neighbor in targets:
                edge = G[src][neighbor]
                rel = edge.get("relation", "unknown")
                violations.append(Violation(
                    rule=rule.name,
                    severity=rule.severity,
                    message=f"{G.nodes[src].get('label', src)} must not depend on "
                            f"{G.nodes[neighbor].get('label', neighbor)} ({rel})",
                    source=src,
                    target=neighbor,
                    details={"relation": rel},
                ))
    return violations


def _check_must_depend(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Source nodes MUST have at least one edge to target nodes."""
    violations = []
    sources = _match_nodes(G, rule.source_pattern)
    targets = set(_match_nodes(G, rule.target_pattern))

    for src in sources:
        neighbors = set(G.neighbors(src))
        if not neighbors & targets:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                message=f"{G.nodes[src].get('label', src)} must depend on at least one "
                        f"node matching '{rule.target_pattern}'",
                source=src,
            ))
    return violations


def _check_max_coupling(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Matched nodes must have at most N external dependencies."""
    violations = []
    threshold = rule.threshold or 10
    sources = _match_nodes(G, rule.source_pattern)

    for src in sources:
        src_file = G.nodes[src].get("file")
        ext_deps = sum(
            1 for n in G.neighbors(src)
            if G.nodes[n].get("file") != src_file
        )
        if ext_deps > threshold:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                message=f"{G.nodes[src].get('label', src)} has {ext_deps} external "
                        f"dependencies (max: {threshold})",
                source=src,
                details={"count": ext_deps, "threshold": threshold},
            ))
    return violations


def _check_max_fan_out(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Matched nodes must have at most N outgoing edges."""
    violations = []
    threshold = rule.threshold or 15
    sources = _match_nodes(G, rule.source_pattern)

    for src in sources:
        fan_out = G.degree(src)
        if fan_out > threshold:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                message=f"{G.nodes[src].get('label', src)} fan-out is {fan_out} (max: {threshold})",
                source=src,
                details={"fan_out": fan_out, "threshold": threshold},
            ))
    return violations


def _check_max_fan_in(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Matched nodes must have at most N incoming edges."""
    violations = []
    threshold = rule.threshold or 15
    targets = _match_nodes(G, rule.target_pattern)

    for tgt in targets:
        if G.is_directed():
            fan_in = G.in_degree(tgt)
        else:
            fan_in = G.degree(tgt)
        if fan_in > threshold:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                message=f"{G.nodes[tgt].get('label', tgt)} fan-in is {fan_in} (max: {threshold})",
                target=tgt,
                details={"fan_in": fan_in, "threshold": threshold},
            ))
    return violations


def _check_layer_order(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Enforce layered architecture: lower layers must not depend on upper layers."""
    violations = []
    layers = rule.layers
    if len(layers) < 2:
        return violations

    # Build layer index: lower index = higher layer
    layer_nodes: dict[int, set[str]] = {}
    node_layer: dict[str, int] = {}

    for idx, layer_pattern in enumerate(layers):
        matched = _match_nodes(G, f"*{layer_pattern}*")
        layer_nodes[idx] = set(matched)
        for node in matched:
            node_layer[node] = idx

    for node, layer_idx in node_layer.items():
        for neighbor in G.neighbors(node):
            n_layer = node_layer.get(neighbor)
            if n_layer is not None and n_layer < layer_idx:
                # Lower layer depending on upper layer — violation
                violations.append(Violation(
                    rule=rule.name,
                    severity=rule.severity,
                    message=f"{layers[layer_idx]} layer ({G.nodes[node].get('label', node)}) "
                            f"depends on {layers[n_layer]} layer ({G.nodes[neighbor].get('label', neighbor)})",
                    source=node,
                    target=neighbor,
                    details={"source_layer": layers[layer_idx], "target_layer": layers[n_layer]},
                ))
    return violations


def _check_no_circular(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """No circular dependencies among matched modules."""
    violations = []
    sources = _match_nodes(G, rule.source_pattern)

    if not sources:
        return violations

    subgraph = G.subgraph(sources)

    # For undirected graphs, find cycles
    if G.is_directed():
        try:
            cycles = list(nx.simple_cycles(subgraph))
        except Exception:
            cycles = []
    else:
        try:
            cycles = nx.cycle_basis(subgraph)
        except Exception:
            cycles = []

    for cycle in cycles[:10]:  # Limit to first 10 cycles
        labels = [G.nodes[n].get("label", n) for n in cycle]
        violations.append(Violation(
            rule=rule.name,
            severity=rule.severity,
            message=f"Circular dependency: {' → '.join(labels)} → {labels[0]}",
            details={"cycle": [str(n) for n in cycle]},
        ))

    return violations


def _check_max_community_size(G: nx.Graph, rule: FitnessRule) -> list[Violation]:
    """Communities must not exceed N nodes."""
    violations = []
    threshold = rule.threshold or 25

    communities: dict[int, list[str]] = {}
    for node, data in G.nodes(data=True):
        comm = data.get("community")
        if comm is not None:
            communities.setdefault(comm, []).append(node)

    for comm_id, members in communities.items():
        if len(members) > threshold:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                message=f"Community {comm_id} has {len(members)} nodes (max: {threshold})",
                details={"community": comm_id, "size": len(members), "threshold": threshold},
            ))

    return violations


def generate_default_rules() -> str:
    """Generate a default neuron-fitness.yaml template."""
    return """# Neuron Architecture Fitness Rules
# Place this file as neuron-fitness.yaml in your project root

rules:
  # Prevent excessive coupling
  - name: max-module-coupling
    kind: max-coupling
    description: No module should have more than 15 external dependencies
    source: "*"
    threshold: 15
    severity: warning

  # Prevent god objects
  - name: max-entity-fan-out
    kind: max-fan-out
    description: No single entity should connect to more than 20 others
    source: "*"
    threshold: 20
    severity: warning

  # Keep communities manageable
  - name: max-community-size
    kind: max-community-size
    threshold: 30
    severity: info

  # Example: layered architecture (uncomment and customize)
  # - name: layered-architecture
  #   kind: layer-order
  #   layers:
  #     - "controller"
  #     - "service"
  #     - "repository"
  #   severity: error

  # Example: prevent UI→DB dependency (uncomment and customize)
  # - name: no-ui-to-db
  #   kind: no-depend
  #   source: "ui/*"
  #   target: "db/*"
  #   severity: error
"""

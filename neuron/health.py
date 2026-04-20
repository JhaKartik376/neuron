"""Code health scoring — coupling, cohesion, complexity metrics per module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


class Grade:
    """Letter grade from A to F based on score 0.0–1.0."""
    THRESHOLDS = [
        (0.9, "A"),
        (0.8, "B"),
        (0.7, "C"),
        (0.6, "D"),
        (0.0, "F"),
    ]

    @staticmethod
    def from_score(score: float) -> str:
        for threshold, grade in Grade.THRESHOLDS:
            if score >= threshold:
                return grade
        return "F"


@dataclass
class ModuleHealth:
    """Health metrics for a single module/file."""
    module: str
    file: str | None

    # Coupling: how much this module depends on others (lower is better)
    afferent_coupling: int = 0   # incoming dependencies (Ca)
    efferent_coupling: int = 0   # outgoing dependencies (Ce)
    instability: float = 0.0     # Ce / (Ca + Ce) — 0=stable, 1=unstable

    # Cohesion: how internally connected the module's entities are
    cohesion: float = 0.0        # 0=scattered, 1=tightly connected

    # Size metrics
    entity_count: int = 0
    function_count: int = 0
    class_count: int = 0

    # Complexity indicators
    max_fan_out: int = 0         # max outgoing edges from any entity
    max_fan_in: int = 0          # max incoming edges to any entity
    god_node_count: int = 0      # entities with degree > 2*avg

    # Computed scores
    coupling_score: float = 0.0  # 0=bad, 1=good
    cohesion_score: float = 0.0  # 0=bad, 1=good
    complexity_score: float = 0.0  # 0=bad, 1=good
    overall_score: float = 0.0
    grade: str = "?"

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "file": self.file,
            "afferent_coupling": self.afferent_coupling,
            "efferent_coupling": self.efferent_coupling,
            "instability": round(self.instability, 3),
            "cohesion": round(self.cohesion, 3),
            "entity_count": self.entity_count,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "max_fan_out": self.max_fan_out,
            "max_fan_in": self.max_fan_in,
            "god_node_count": self.god_node_count,
            "coupling_score": round(self.coupling_score, 3),
            "cohesion_score": round(self.cohesion_score, 3),
            "complexity_score": round(self.complexity_score, 3),
            "overall_score": round(self.overall_score, 3),
            "grade": self.grade,
        }


@dataclass
class HealthReport:
    """Aggregated health report for the entire codebase."""
    modules: list[ModuleHealth] = field(default_factory=list)
    overall_score: float = 0.0
    grade: str = "?"
    hotspots: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 3),
            "grade": self.grade,
            "modules": [m.to_dict() for m in self.modules],
            "hotspots": self.hotspots,
            "recommendations": self.recommendations,
        }


def compute_health(G: nx.Graph) -> HealthReport:
    """Compute health metrics for every module in the graph.

    Analyzes coupling, cohesion, and complexity to produce per-module
    scores and an overall codebase health grade.
    """
    report = HealthReport()

    # Group nodes by file/module
    modules: dict[str, list[str]] = {}
    for node, data in G.nodes(data=True):
        f = data.get("file")
        if f:
            modules.setdefault(f, []).append(node)

    if not modules:
        return report

    # Compute per-module health
    avg_degree = sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1)
    god_threshold = max(avg_degree * 2, 3)

    for filepath, members in modules.items():
        member_set = set(members)
        mh = ModuleHealth(
            module=filepath.rsplit("/", 1)[-1].rsplit(".", 1)[0],
            file=filepath,
        )

        # Count entity types
        for node in members:
            data = G.nodes[node]
            kind = data.get("kind", "")
            mh.entity_count += 1
            if kind in ("function", "method"):
                mh.function_count += 1
            elif kind == "class":
                mh.class_count += 1

        # Coupling: count edges crossing module boundary
        for node in members:
            for neighbor in G.neighbors(node):
                n_file = G.nodes[neighbor].get("file")
                if n_file and n_file != filepath:
                    # Check edge direction for afferent vs efferent
                    if G.is_directed():
                        if G.has_edge(node, neighbor):
                            mh.efferent_coupling += 1
                        if G.has_edge(neighbor, node):
                            mh.afferent_coupling += 1
                    else:
                        edge_data = G[node][neighbor]
                        rel = edge_data.get("relation", "")
                        if "imports" in rel or "calls" in rel or "depends_on" in rel:
                            mh.efferent_coupling += 1
                        else:
                            mh.afferent_coupling += 1

        total_coupling = mh.afferent_coupling + mh.efferent_coupling
        mh.instability = mh.efferent_coupling / total_coupling if total_coupling > 0 else 0.5

        # Cohesion: internal connectivity density
        subgraph = G.subgraph(members)
        internal_edges = subgraph.number_of_edges()
        n = len(members)
        max_internal = n * (n - 1) / 2
        mh.cohesion = internal_edges / max_internal if max_internal > 0 else 1.0

        # Fan-in / fan-out per entity
        for node in members:
            degree = G.degree(node)
            out_edges = sum(
                1 for neighbor in G.neighbors(node)
                if G.nodes[neighbor].get("file") != filepath
            )
            in_edges = degree - out_edges
            mh.max_fan_out = max(mh.max_fan_out, out_edges)
            mh.max_fan_in = max(mh.max_fan_in, in_edges)
            if degree >= god_threshold:
                mh.god_node_count += 1

        # Compute scores (0=bad, 1=good)
        # Coupling score: penalize high efferent coupling
        mh.coupling_score = max(0, 1.0 - (mh.efferent_coupling / max(mh.entity_count * 3, 1)))
        mh.coupling_score = min(mh.coupling_score, 1.0)

        # Cohesion score: reward high internal connectivity
        mh.cohesion_score = min(mh.cohesion * 2, 1.0)  # Scale up since density is usually low

        # Complexity score: penalize god nodes and extreme fan-out
        god_penalty = mh.god_node_count / max(mh.entity_count, 1)
        fan_penalty = min(mh.max_fan_out / 20, 1.0)
        mh.complexity_score = max(0, 1.0 - god_penalty * 0.5 - fan_penalty * 0.5)

        # Overall: weighted average
        mh.overall_score = (
            mh.coupling_score * 0.35
            + mh.cohesion_score * 0.30
            + mh.complexity_score * 0.35
        )
        mh.grade = Grade.from_score(mh.overall_score)

        report.modules.append(mh)

    # Sort by score ascending (worst first)
    report.modules.sort(key=lambda m: m.overall_score)

    # Overall codebase score
    if report.modules:
        scores = [m.overall_score for m in report.modules]
        report.overall_score = sum(scores) / len(scores)
        report.grade = Grade.from_score(report.overall_score)

    # Identify hotspots (worst modules)
    for m in report.modules[:5]:
        if m.overall_score < 0.7:
            issues = []
            if m.coupling_score < 0.6:
                issues.append(f"high coupling (Ce={m.efferent_coupling})")
            if m.cohesion_score < 0.5:
                issues.append(f"low cohesion ({m.cohesion:.2f})")
            if m.complexity_score < 0.6:
                issues.append(f"complexity (god_nodes={m.god_node_count}, max_fan_out={m.max_fan_out})")
            if issues:
                report.hotspots.append({
                    "module": m.module,
                    "file": m.file,
                    "grade": m.grade,
                    "score": round(m.overall_score, 3),
                    "issues": issues,
                })

    # Generate recommendations
    report.recommendations = _generate_recommendations(report)

    return report


def _generate_recommendations(report: HealthReport) -> list[str]:
    """Generate actionable recommendations based on health metrics."""
    recs = []

    # Find modules with specific issues
    high_coupling = [m for m in report.modules if m.coupling_score < 0.5]
    low_cohesion = [m for m in report.modules if m.cohesion_score < 0.3]
    high_complexity = [m for m in report.modules if m.complexity_score < 0.5]

    if high_coupling:
        names = ", ".join(m.module for m in high_coupling[:3])
        recs.append(
            f"Reduce coupling in [{names}]: extract shared interfaces or introduce "
            "a mediator to decouple direct dependencies."
        )

    if low_cohesion:
        names = ", ".join(m.module for m in low_cohesion[:3])
        recs.append(
            f"Improve cohesion in [{names}]: consider splitting these modules — "
            "their internal entities are loosely related."
        )

    if high_complexity:
        for m in high_complexity[:3]:
            if m.god_node_count > 0:
                recs.append(
                    f"Decompose god nodes in {m.module}: {m.god_node_count} entities "
                    f"have excessive connections (max fan-out: {m.max_fan_out})."
                )

    # Instability analysis
    unstable = [m for m in report.modules if m.instability > 0.8 and m.entity_count > 3]
    stable = [m for m in report.modules if m.instability < 0.2 and m.entity_count > 3]

    if unstable:
        names = ", ".join(m.module for m in unstable[:3])
        recs.append(
            f"Highly unstable modules [{names}]: these depend on many others but few depend on them. "
            "Consider if they should be more stable (depended-upon) or are correctly volatile."
        )

    if not recs:
        recs.append("Codebase health looks good. No critical issues detected.")

    return recs

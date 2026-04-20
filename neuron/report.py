"""Generate NEURON_REPORT.md with health scores, fitness violations, and refactoring suggestions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import networkx as nx

from .analyze import AnalysisResult
from .build import graph_stats
from .fitness import FitnessReport
from .health import HealthReport


def generate_report(
    G: nx.Graph,
    analysis: AnalysisResult,
    health: HealthReport,
    fitness: FitnessReport | None = None,
    cluster_info: dict[str, Any] | None = None,
    output_dir: str = ".",
) -> str:
    """Generate a comprehensive NEURON_REPORT.md.

    Returns the report content as a string.
    """
    stats = graph_stats(G)
    lines: list[str] = []

    def _h1(text: str):
        lines.append(f"# {text}\n")

    def _h2(text: str):
        lines.append(f"## {text}\n")

    def _h3(text: str):
        lines.append(f"### {text}\n")

    def _p(text: str):
        lines.append(f"{text}\n")

    def _bullet(text: str):
        lines.append(f"- {text}")

    def _blank():
        lines.append("")

    # ── Header ───────────────────────────────────────────────────────
    _h1("Neuron Report")
    _p(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    _blank()

    # ── Health Dashboard ─────────────────────────────────────────────
    _h2(f"Health: {health.grade} ({health.overall_score:.0%})")
    _blank()

    _p("| Metric | Value |")
    _p("|--------|-------|")
    _p(f"| Nodes | {stats['nodes']} |")
    _p(f"| Edges | {stats['edges']} |")
    _p(f"| Density | {stats['density']:.4f} |")
    _p(f"| Components | {stats['components']} |")
    _p(f"| Communities | {cluster_info['stats']['count'] if cluster_info else 'N/A'} |")
    _p(f"| Overall Grade | **{health.grade}** |")
    _blank()

    # ── Module Health Table ──────────────────────────────────────────
    if health.modules:
        _h2("Module Health Scores")
        _blank()
        _p("| Module | Grade | Coupling | Cohesion | Complexity | Score |")
        _p("|--------|-------|----------|----------|------------|-------|")

        for m in health.modules:
            _p(f"| {m.module} | {m.grade} | {m.coupling_score:.2f} | "
               f"{m.cohesion_score:.2f} | {m.complexity_score:.2f} | {m.overall_score:.2f} |")
        _blank()

    # ── Hotspots ─────────────────────────────────────────────────────
    if health.hotspots:
        _h2("Hotspots")
        _blank()
        for h in health.hotspots:
            _bullet(f"**{h['module']}** ({h['grade']}, {h['score']:.2f}): {', '.join(h['issues'])}")
        _blank()

    # ── Fitness Rules ────────────────────────────────────────────────
    if fitness:
        _h2(f"Architecture Fitness ({fitness.passed}/{fitness.rules_checked} rules passed)")
        _blank()

        if fitness.violations:
            for v in fitness.violations:
                icon = "!!" if v.severity == "error" else "?" if v.severity == "warning" else "i"
                _bullet(f"[{icon}] **{v.rule}**: {v.message}")
            _blank()
        else:
            _p("All architecture fitness rules passed.")
            _blank()

    # ── God Nodes ────────────────────────────────────────────────────
    if analysis.god_nodes:
        _h2("God Nodes (High Connectivity)")
        _blank()
        _p("| Node | Kind | Degree | Betweenness | Risk |")
        _p("|------|------|--------|-------------|------|")
        for g in analysis.god_nodes:
            risk_icon = "!!" if g.risk_score > 0.5 else "!" if g.risk_score > 0.3 else ""
            _p(f"| {g.label} | {g.kind} | {g.degree} | "
               f"{g.betweenness:.3f} | {g.risk_score:.2f} {risk_icon} |")
        _blank()

    # ── Bridge Nodes ─────────────────────────────────────────────────
    if analysis.bridge_nodes:
        _h2("Bridge Nodes")
        _blank()
        for b in analysis.bridge_nodes[:5]:
            comms = ", ".join(str(c) for c in b.communities_bridged)
            _bullet(f"**{b.label}** ({b.kind}): bridges communities [{comms}], score={b.bridge_score:.2f}")
        _blank()

    # ── Surprising Connections ───────────────────────────────────────
    if analysis.surprising_connections:
        _h2("Surprising Connections")
        _blank()
        for s in analysis.surprising_connections[:10]:
            _bullet(f"**{s.source}** → **{s.target}** ({s.relation}): {s.reason} "
                    f"[score={s.surprise_score:.2f}]")
        _blank()

    # ── Communities ──────────────────────────────────────────────────
    if cluster_info and "communities" in cluster_info:
        _h2("Communities")
        _blank()
        hierarchy = cluster_info.get("hierarchy", {})
        for cid, members in sorted(cluster_info["communities"].items()):
            h_info = hierarchy.get(cid, {})
            cohesion = h_info.get("cohesion", 0)
            kinds = h_info.get("dominant_kinds", {})
            dominant = max(kinds, key=kinds.get) if kinds else "mixed"
            _h3(f"Community {cid} ({len(members)} nodes, cohesion={cohesion:.2f}, type={dominant})")
            # Show top nodes by degree
            member_degrees = [(m, G.degree(m)) for m in members if m in G]
            member_degrees.sort(key=lambda x: -x[1])
            for m, d in member_degrees[:5]:
                label = G.nodes[m].get("label", m)
                _bullet(f"{label} (degree={d})")
            if len(members) > 5:
                _p(f"  *...and {len(members) - 5} more*")
            _blank()

    # ── Recommendations ──────────────────────────────────────────────
    _h2("Recommendations")
    _blank()
    if health.recommendations:
        for rec in health.recommendations:
            _bullet(rec)
    _blank()

    # ── Suggested Questions ──────────────────────────────────────────
    if analysis.suggested_questions:
        _h2("Suggested Questions")
        _blank()
        for q in analysis.suggested_questions:
            _bullet(q)
        _blank()

    # ── Confidence Breakdown ─────────────────────────────────────────
    if stats.get("confidence_breakdown"):
        _h2("Confidence Breakdown")
        _blank()
        for conf, count in stats["confidence_breakdown"].items():
            pct = count / max(stats["edges"], 1) * 100
            _bullet(f"**{conf}**: {count} edges ({pct:.1f}%)")
        _blank()

    _p("---")
    _p("*Generated by [Neuron](https://github.com/kartikjha/neuron)*")

    return "\n".join(lines)

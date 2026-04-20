"""Graph analysis: centrality metrics, god nodes, surprising connections, bridge detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


@dataclass
class GodNode:
    """A node with disproportionately high connectivity."""
    node_id: str
    label: str
    degree: int
    kind: str
    betweenness: float
    eigenvector: float
    community: int | None
    file: str | None
    risk_score: float = 0.0  # How risky is this god node (coupling indicator)


@dataclass
class SurprisingConnection:
    """An unexpected edge connecting distant parts of the graph."""
    source: str
    target: str
    source_community: int | None
    target_community: int | None
    relation: str
    surprise_score: float
    reason: str


@dataclass
class BridgeNode:
    """A node that bridges multiple communities."""
    node_id: str
    label: str
    communities_bridged: list[int]
    bridge_score: float
    kind: str


@dataclass
class AnalysisResult:
    god_nodes: list[GodNode] = field(default_factory=list)
    surprising_connections: list[SurprisingConnection] = field(default_factory=list)
    bridge_nodes: list[BridgeNode] = field(default_factory=list)
    centrality: dict[str, dict[str, float]] = field(default_factory=dict)
    suggested_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "god_nodes": [
                {
                    "id": g.node_id, "label": g.label, "degree": g.degree,
                    "kind": g.kind, "betweenness": round(g.betweenness, 4),
                    "eigenvector": round(g.eigenvector, 4),
                    "community": g.community, "risk_score": round(g.risk_score, 3),
                }
                for g in self.god_nodes
            ],
            "surprising_connections": [
                {
                    "source": s.source, "target": s.target,
                    "source_community": s.source_community,
                    "target_community": s.target_community,
                    "relation": s.relation,
                    "surprise_score": round(s.surprise_score, 3),
                    "reason": s.reason,
                }
                for s in self.surprising_connections
            ],
            "bridge_nodes": [
                {
                    "id": b.node_id, "label": b.label,
                    "communities_bridged": b.communities_bridged,
                    "bridge_score": round(b.bridge_score, 3),
                    "kind": b.kind,
                }
                for b in self.bridge_nodes
            ],
            "suggested_questions": self.suggested_questions,
        }


def analyze(G: nx.Graph, top_n: int = 10) -> AnalysisResult:
    """Run full analysis on the knowledge graph.

    Computes centrality metrics, identifies god nodes, surprising connections,
    and bridge nodes.
    """
    result = AnalysisResult()

    if G.number_of_nodes() == 0:
        return result

    # Work on undirected for centrality
    H = G.to_undirected() if G.is_directed() else G

    # ── Centrality metrics ───────────────────────────────────────────
    degree_cent = nx.degree_centrality(H)
    betweenness = nx.betweenness_centrality(H, k=min(100, H.number_of_nodes()))

    try:
        eigenvector = nx.eigenvector_centrality(H, max_iter=300, tol=1e-4)
    except (nx.PowerIterationFailedConvergence, nx.NetworkXError):
        eigenvector = {n: 0.0 for n in H.nodes()}

    closeness = nx.closeness_centrality(H)

    result.centrality = {
        node: {
            "degree": round(degree_cent.get(node, 0), 4),
            "betweenness": round(betweenness.get(node, 0), 4),
            "eigenvector": round(eigenvector.get(node, 0), 4),
            "closeness": round(closeness.get(node, 0), 4),
        }
        for node in G.nodes()
    }

    # ── God nodes ────────────────────────────────────────────────────
    avg_degree = sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1)
    threshold = max(avg_degree * 2, 3)

    candidates = [
        (node, G.degree(node))
        for node in G.nodes()
        if G.degree(node) >= threshold
    ]
    candidates.sort(key=lambda x: -x[1])

    for node, degree in candidates[:top_n]:
        data = G.nodes[node]
        # Risk score: higher betweenness + high degree = potential bottleneck
        risk = (
            betweenness.get(node, 0) * 0.6
            + degree_cent.get(node, 0) * 0.4
        )
        result.god_nodes.append(GodNode(
            node_id=node,
            label=data.get("label", node),
            degree=degree,
            kind=data.get("kind", "unknown"),
            betweenness=betweenness.get(node, 0),
            eigenvector=eigenvector.get(node, 0),
            community=data.get("community"),
            file=data.get("file"),
            risk_score=risk,
        ))

    # ── Surprising connections ───────────────────────────────────────
    result.surprising_connections = _find_surprising(G, betweenness, top_n)

    # ── Bridge nodes ─────────────────────────────────────────────────
    result.bridge_nodes = _find_bridges(G, betweenness, top_n)

    # ── Suggested questions ──────────────────────────────────────────
    result.suggested_questions = _generate_questions(G, result)

    return result


def _find_surprising(
    G: nx.Graph,
    betweenness: dict[str, float],
    top_n: int,
) -> list[SurprisingConnection]:
    """Find edges that connect distant/unexpected parts of the graph."""
    surprising = []

    for u, v, data in G.edges(data=True):
        u_data = G.nodes.get(u, {})
        v_data = G.nodes.get(v, {})
        u_comm = u_data.get("community")
        v_comm = v_data.get("community")

        # Skip intra-community edges (not surprising)
        if u_comm is not None and u_comm == v_comm:
            continue

        # Skip "contains" relations (structural, not surprising)
        relation = data.get("relation", "")
        if relation == "contains":
            continue

        # Compute surprise score
        score = 0.0

        # Cross-community bonus
        if u_comm is not None and v_comm is not None and u_comm != v_comm:
            score += 0.4

        # Cross-file bonus
        u_file = u_data.get("file")
        v_file = v_data.get("file")
        if u_file and v_file and u_file != v_file:
            score += 0.2

        # Cross-kind bonus (e.g., function calling a class from different domain)
        if u_data.get("kind") != v_data.get("kind"):
            score += 0.1

        # Betweenness bonus (if either endpoint is high-betweenness)
        u_bet = betweenness.get(u, 0)
        v_bet = betweenness.get(v, 0)
        score += min(u_bet + v_bet, 0.3)

        if score < 0.3:
            continue

        reason_parts = []
        if u_comm != v_comm:
            reason_parts.append(f"cross-community ({u_comm}→{v_comm})")
        if u_file != v_file:
            reason_parts.append("cross-file")
        if u_bet > 0.1 or v_bet > 0.1:
            reason_parts.append("high-betweenness endpoint")

        surprising.append(SurprisingConnection(
            source=u_data.get("label", u),
            target=v_data.get("label", v),
            source_community=u_comm,
            target_community=v_comm,
            relation=relation,
            surprise_score=score,
            reason="; ".join(reason_parts),
        ))

    surprising.sort(key=lambda s: -s.surprise_score)
    return surprising[:top_n]


def _find_bridges(
    G: nx.Graph,
    betweenness: dict[str, float],
    top_n: int,
) -> list[BridgeNode]:
    """Find nodes that bridge multiple communities."""
    bridges = []

    for node in G.nodes():
        data = G.nodes[node]
        node_comm = data.get("community")

        neighbor_comms = set()
        for neighbor in G.neighbors(node):
            n_comm = G.nodes[neighbor].get("community")
            if n_comm is not None and n_comm != node_comm:
                neighbor_comms.add(n_comm)

        if len(neighbor_comms) < 2:
            continue

        # Bridge score: number of communities bridged * betweenness
        score = len(neighbor_comms) * (1 + betweenness.get(node, 0) * 10)

        all_comms = sorted(neighbor_comms)
        if node_comm is not None:
            all_comms = sorted({node_comm} | neighbor_comms)

        bridges.append(BridgeNode(
            node_id=node,
            label=data.get("label", node),
            communities_bridged=all_comms,
            bridge_score=score,
            kind=data.get("kind", "unknown"),
        ))

    bridges.sort(key=lambda b: -b.bridge_score)
    return bridges[:top_n]


def _generate_questions(G: nx.Graph, result: AnalysisResult) -> list[str]:
    """Generate investigation questions based on analysis findings."""
    questions = []

    # God node questions
    for g in result.god_nodes[:3]:
        if g.risk_score > 0.3:
            questions.append(
                f"Why does {g.label} have {g.degree} connections? "
                f"Is it doing too much (risk score: {g.risk_score:.2f})?"
            )

    # Bridge node questions
    for b in result.bridge_nodes[:3]:
        comms = ", ".join(str(c) for c in b.communities_bridged)
        questions.append(
            f"Should {b.label} be split? It bridges communities [{comms}]."
        )

    # Surprising connection questions
    for s in result.surprising_connections[:3]:
        questions.append(
            f"Why does {s.source} connect to {s.target}? ({s.reason})"
        )

    # General structural questions
    if result.god_nodes:
        max_degree = result.god_nodes[0].degree
        avg_degree = sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1)
        if max_degree > avg_degree * 5:
            questions.append(
                f"The max degree ({max_degree}) is {max_degree/avg_degree:.1f}x the average ({avg_degree:.1f}). "
                "Is there a missing abstraction layer?"
            )

    return questions

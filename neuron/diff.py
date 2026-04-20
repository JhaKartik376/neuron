"""Graph diffing — compare knowledge graphs across branches, commits, or snapshots."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


@dataclass
class NodeChange:
    node_id: str
    label: str
    change: str  # added, removed, modified
    kind: str
    old_attrs: dict[str, Any] = field(default_factory=dict)
    new_attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeChange:
    source: str
    target: str
    change: str  # added, removed, modified
    relation: str
    old_attrs: dict[str, Any] = field(default_factory=dict)
    new_attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommunityChange:
    community_id: int
    change: str  # grew, shrunk, split, merged, new, removed
    old_size: int = 0
    new_size: int = 0
    nodes_added: list[str] = field(default_factory=list)
    nodes_removed: list[str] = field(default_factory=list)


@dataclass
class GraphDiff:
    """Result of diffing two graph snapshots."""
    node_changes: list[NodeChange] = field(default_factory=list)
    edge_changes: list[EdgeChange] = field(default_factory=list)
    community_changes: list[CommunityChange] = field(default_factory=list)

    # Summary stats
    nodes_added: int = 0
    nodes_removed: int = 0
    nodes_modified: int = 0
    edges_added: int = 0
    edges_removed: int = 0
    edges_modified: int = 0

    # Structural drift
    drift_score: float = 0.0  # 0=identical, 1=completely different

    old_stats: dict[str, Any] = field(default_factory=dict)
    new_stats: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        if self.nodes_added:
            parts.append(f"+{self.nodes_added} nodes")
        if self.nodes_removed:
            parts.append(f"-{self.nodes_removed} nodes")
        if self.nodes_modified:
            parts.append(f"~{self.nodes_modified} modified")
        if self.edges_added:
            parts.append(f"+{self.edges_added} edges")
        if self.edges_removed:
            parts.append(f"-{self.edges_removed} edges")
        parts.append(f"drift={self.drift_score:.2%}")
        return ", ".join(parts) if parts else "no changes"

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "drift_score": round(self.drift_score, 4),
            "nodes_added": self.nodes_added,
            "nodes_removed": self.nodes_removed,
            "nodes_modified": self.nodes_modified,
            "edges_added": self.edges_added,
            "edges_removed": self.edges_removed,
            "edges_modified": self.edges_modified,
            "node_changes": [
                {
                    "id": c.node_id, "label": c.label, "change": c.change,
                    "kind": c.kind,
                }
                for c in self.node_changes[:50]
            ],
            "edge_changes": [
                {
                    "source": c.source, "target": c.target, "change": c.change,
                    "relation": c.relation,
                }
                for c in self.edge_changes[:50]
            ],
            "community_changes": [
                {
                    "id": c.community_id, "change": c.change,
                    "old_size": c.old_size, "new_size": c.new_size,
                }
                for c in self.community_changes
            ],
        }


def diff_graphs(old: nx.Graph, new: nx.Graph) -> GraphDiff:
    """Compute the diff between two graph snapshots.

    Args:
        old: The previous graph state.
        new: The current graph state.

    Returns:
        A GraphDiff with all changes between the two graphs.
    """
    result = GraphDiff()

    old_nodes = set(old.nodes())
    new_nodes = set(new.nodes())

    # ── Node changes ─────────────────────────────────────────────────
    added = new_nodes - old_nodes
    removed = old_nodes - new_nodes
    common = old_nodes & new_nodes

    result.nodes_added = len(added)
    result.nodes_removed = len(removed)

    for node in added:
        data = new.nodes[node]
        result.node_changes.append(NodeChange(
            node_id=node,
            label=data.get("label", node),
            change="added",
            kind=data.get("kind", "unknown"),
            new_attrs=dict(data),
        ))

    for node in removed:
        data = old.nodes[node]
        result.node_changes.append(NodeChange(
            node_id=node,
            label=data.get("label", node),
            change="removed",
            kind=data.get("kind", "unknown"),
            old_attrs=dict(data),
        ))

    # Check modified nodes
    for node in common:
        old_data = dict(old.nodes[node])
        new_data = dict(new.nodes[node])
        # Compare significant attributes
        changed = False
        for key in ("kind", "file", "community", "docstring", "signature"):
            if old_data.get(key) != new_data.get(key):
                changed = True
                break
        # Check degree change
        if old.degree(node) != new.degree(node):
            changed = True

        if changed:
            result.nodes_modified += 1
            result.node_changes.append(NodeChange(
                node_id=node,
                label=new_data.get("label", node),
                change="modified",
                kind=new_data.get("kind", "unknown"),
                old_attrs=old_data,
                new_attrs=new_data,
            ))

    # ── Edge changes ─────────────────────────────────────────────────
    old_edges = set(old.edges())
    new_edges = set(new.edges())

    added_edges = new_edges - old_edges
    removed_edges = old_edges - new_edges
    common_edges = old_edges & new_edges

    result.edges_added = len(added_edges)
    result.edges_removed = len(removed_edges)

    for u, v in added_edges:
        data = new[u][v]
        result.edge_changes.append(EdgeChange(
            source=new.nodes.get(u, {}).get("label", u),
            target=new.nodes.get(v, {}).get("label", v),
            change="added",
            relation=data.get("relation", "unknown"),
            new_attrs=dict(data),
        ))

    for u, v in removed_edges:
        data = old[u][v]
        result.edge_changes.append(EdgeChange(
            source=old.nodes.get(u, {}).get("label", u),
            target=old.nodes.get(v, {}).get("label", v),
            change="removed",
            relation=data.get("relation", "unknown"),
            old_attrs=dict(data),
        ))

    for u, v in common_edges:
        old_data = dict(old[u][v])
        new_data = dict(new[u][v])
        if old_data.get("relation") != new_data.get("relation") or old_data.get("confidence") != new_data.get("confidence"):
            result.edges_modified += 1
            result.edge_changes.append(EdgeChange(
                source=new.nodes.get(u, {}).get("label", u),
                target=new.nodes.get(v, {}).get("label", v),
                change="modified",
                relation=new_data.get("relation", "unknown"),
                old_attrs=old_data,
                new_attrs=new_data,
            ))

    # ── Community changes ────────────────────────────────────────────
    result.community_changes = _diff_communities(old, new)

    # ── Structural drift score ───────────────────────────────────────
    total_changes = (
        result.nodes_added + result.nodes_removed + result.nodes_modified
        + result.edges_added + result.edges_removed + result.edges_modified
    )
    total_elements = max(
        len(old_nodes) + old.number_of_edges() + len(new_nodes) + new.number_of_edges(),
        1,
    )
    result.drift_score = min(total_changes / total_elements, 1.0)

    # Stats
    result.old_stats = {"nodes": len(old_nodes), "edges": old.number_of_edges()}
    result.new_stats = {"nodes": len(new_nodes), "edges": new.number_of_edges()}

    return result


def _diff_communities(old: nx.Graph, new: nx.Graph) -> list[CommunityChange]:
    """Diff community assignments between two graphs."""
    changes = []

    def _get_communities(G: nx.Graph) -> dict[int, set[str]]:
        comms: dict[int, set[str]] = {}
        for node, data in G.nodes(data=True):
            c = data.get("community")
            if c is not None:
                comms.setdefault(c, set()).add(node)
        return comms

    old_comms = _get_communities(old)
    new_comms = _get_communities(new)

    all_ids = set(old_comms.keys()) | set(new_comms.keys())

    for cid in all_ids:
        old_members = old_comms.get(cid, set())
        new_members = new_comms.get(cid, set())

        if not old_members:
            changes.append(CommunityChange(
                community_id=cid, change="new",
                new_size=len(new_members),
                nodes_added=sorted(new_members),
            ))
        elif not new_members:
            changes.append(CommunityChange(
                community_id=cid, change="removed",
                old_size=len(old_members),
                nodes_removed=sorted(old_members),
            ))
        elif old_members != new_members:
            added = new_members - old_members
            removed = old_members - new_members
            change_type = "grew" if len(new_members) > len(old_members) else "shrunk"
            changes.append(CommunityChange(
                community_id=cid, change=change_type,
                old_size=len(old_members),
                new_size=len(new_members),
                nodes_added=sorted(added),
                nodes_removed=sorted(removed),
            ))

    return changes


def load_graph_snapshot(path: str | Path) -> nx.Graph:
    """Load a graph from a JSON snapshot file."""
    path = Path(path)
    data = json.loads(path.read_text())
    return json_graph.node_link_graph(data)


def diff_from_files(old_path: str | Path, new_path: str | Path) -> GraphDiff:
    """Diff two graph JSON files."""
    old = load_graph_snapshot(old_path)
    new = load_graph_snapshot(new_path)
    return diff_graphs(old, new)


def diff_from_git(
    repo_path: str | Path,
    old_ref: str = "HEAD~1",
    new_ref: str = "HEAD",
    graph_path: str = ".neuron-out/graph.json",
) -> GraphDiff | None:
    """Diff graph snapshots across two git refs.

    Checks out the graph.json from each ref and compares them.
    """
    repo_path = Path(repo_path)

    def _git_show(ref: str, file_path: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{file_path}"],
                capture_output=True, text=True, cwd=repo_path,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
        return None

    old_json = _git_show(old_ref, graph_path)
    new_json = _git_show(new_ref, graph_path)

    if old_json is None or new_json is None:
        return None

    old_data = json.loads(old_json)
    new_data = json.loads(new_json)

    old_graph = json_graph.node_link_graph(old_data)
    new_graph = json_graph.node_link_graph(new_data)

    return diff_graphs(old_graph, new_graph)

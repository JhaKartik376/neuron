"""Build a NetworkX knowledge graph from extraction results."""

from __future__ import annotations

import re
from typing import Any

import networkx as nx

from .extract import Confidence, ExtractionResult


def _normalize_id(name: str) -> str:
    """Normalize a name into a stable node ID."""
    return re.sub(r"[^a-zA-Z0-9_./]", "_", name.strip()).lower()


def _resolve_cross_file_target(target: str, all_entities: dict[str, dict]) -> str | None:
    """Try to resolve a target name to a known entity across files."""
    norm = _normalize_id(target)
    if norm in all_entities:
        return norm

    # Try partial matching (e.g., "MyClass" matches "mymodule.MyClass")
    for eid in all_entities:
        if eid.endswith(f".{norm}") or eid.endswith(f"/{norm}"):
            return eid

    # Try case-insensitive basename match
    base = norm.rsplit(".", 1)[-1] if "." in norm else norm
    for eid in all_entities:
        eid_base = eid.rsplit(".", 1)[-1] if "." in eid else eid
        if eid_base == base:
            return eid

    return None


def build_graph(
    extractions: list[ExtractionResult],
    directed: bool = False,
    resolve_cross_file: bool = True,
) -> nx.Graph:
    """Build a knowledge graph from extraction results.

    Args:
        extractions: List of per-file extraction results.
        directed: Whether to build a directed graph (DiGraph).
        resolve_cross_file: Whether to resolve cross-file references.

    Returns:
        A NetworkX graph with entities as nodes and relations as edges.
    """
    G = nx.DiGraph() if directed else nx.Graph()

    # Phase 1: Add all entities as nodes
    all_entities: dict[str, dict] = {}
    for ext in extractions:
        for entity in ext.entities:
            nid = _normalize_id(entity.name)
            attrs: dict[str, Any] = {
                "label": entity.name,
                "kind": entity.kind,
                "file": entity.file,
                "line": entity.line,
                "end_line": entity.end_line,
                "visibility": entity.visibility,
            }
            if entity.docstring:
                attrs["docstring"] = entity.docstring
            if entity.signature:
                attrs["signature"] = entity.signature
            if entity.decorators:
                attrs["decorators"] = entity.decorators
            if entity.metadata:
                attrs["metadata"] = entity.metadata

            if nid in all_entities:
                # Merge: prefer the richer record
                existing = all_entities[nid]
                for k, v in attrs.items():
                    if v is not None and (k not in existing or existing[k] is None):
                        existing[k] = v
                all_entities[nid] = existing
            else:
                all_entities[nid] = attrs

    for nid, attrs in all_entities.items():
        G.add_node(nid, **attrs)

    # Phase 2: Add relations as edges
    unresolved_targets: set[str] = set()

    for ext in extractions:
        for rel in ext.relations:
            src_id = _normalize_id(rel.source)
            tgt_id = _normalize_id(rel.target)

            # Ensure source exists
            if src_id not in G:
                G.add_node(src_id, label=rel.source, kind="unknown", file=rel.file)

            # Resolve target
            if tgt_id not in G:
                if resolve_cross_file:
                    resolved = _resolve_cross_file_target(rel.target, all_entities)
                    if resolved:
                        tgt_id = resolved
                    else:
                        # Add as external reference node
                        G.add_node(tgt_id, label=rel.target, kind="external", file=None)
                        unresolved_targets.add(tgt_id)
                else:
                    G.add_node(tgt_id, label=rel.target, kind="external", file=None)

            # Skip self-loops
            if src_id == tgt_id:
                continue

            edge_attrs: dict[str, Any] = {
                "relation": rel.kind,
                "confidence": rel.confidence.value,
                "score": rel.score,
            }
            if rel.file:
                edge_attrs["file"] = rel.file
            if rel.metadata:
                edge_attrs["metadata"] = rel.metadata

            # Handle multi-edges: if edge exists, keep both relation types
            if G.has_edge(src_id, tgt_id):
                existing = G[src_id][tgt_id]
                existing_rel = existing.get("relation", "")
                if rel.kind not in existing_rel:
                    existing["relation"] = f"{existing_rel},{rel.kind}"
                # Keep highest confidence score
                if rel.score > existing.get("score", 0):
                    existing["score"] = rel.score
            else:
                G.add_edge(src_id, tgt_id, **edge_attrs)

    # Store graph metadata
    G.graph["unresolved_count"] = len(unresolved_targets)
    G.graph["entity_count"] = len(all_entities)
    G.graph["file_count"] = len(extractions)

    return G


def prune_graph(
    G: nx.Graph,
    min_degree: int = 0,
    remove_external: bool = False,
    remove_kinds: set[str] | None = None,
) -> nx.Graph:
    """Remove nodes from the graph based on criteria.

    Args:
        G: Input graph.
        min_degree: Remove nodes with degree below this threshold.
        remove_external: Remove nodes with kind="external".
        remove_kinds: Remove nodes matching these kinds.

    Returns:
        A new pruned graph.
    """
    to_remove = set()

    for node, data in G.nodes(data=True):
        if min_degree > 0 and G.degree(node) < min_degree:
            to_remove.add(node)
        if remove_external and data.get("kind") == "external":
            to_remove.add(node)
        if remove_kinds and data.get("kind") in remove_kinds:
            to_remove.add(node)

    H = G.copy()
    H.remove_nodes_from(to_remove)
    return H


def graph_stats(G: nx.Graph) -> dict[str, Any]:
    """Compute basic graph statistics."""
    kinds: dict[str, int] = {}
    relations: dict[str, int] = {}
    confidence: dict[str, int] = {}

    for _, data in G.nodes(data=True):
        k = data.get("kind", "unknown")
        kinds[k] = kinds.get(k, 0) + 1

    for _, _, data in G.edges(data=True):
        for r in data.get("relation", "unknown").split(","):
            relations[r] = relations.get(r, 0) + 1
        c = data.get("confidence", "unknown")
        confidence[c] = confidence.get(c, 0) + 1

    stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "components": nx.number_connected_components(G) if not G.is_directed() else nx.number_weakly_connected_components(G),
        "node_kinds": kinds,
        "edge_relations": relations,
        "confidence_breakdown": confidence,
    }

    return stats

"""Hierarchical community detection using Leiden/Louvain with nested sub-communities."""

from __future__ import annotations

from typing import Any

import networkx as nx


def _try_leiden(G: nx.Graph, resolution: float = 1.0) -> dict[str, int] | None:
    """Attempt Leiden clustering via graspologic."""
    try:
        from graspologic.partition import leiden

        node_list = list(G.nodes())
        if len(node_list) < 2:
            return None

        partition = leiden(G, resolution=resolution)
        return {str(node): int(comm) for node, comm in partition.items()}
    except ImportError:
        return None
    except Exception:
        return None


def _louvain(G: nx.Graph, resolution: float = 1.0) -> dict[str, int]:
    """Louvain clustering using built-in NetworkX."""
    if G.number_of_nodes() < 2:
        return {n: 0 for n in G.nodes()}

    # NetworkX Louvain returns list of sets
    communities = nx.community.louvain_communities(
        G, resolution=resolution, seed=42
    )
    mapping = {}
    for idx, comm in enumerate(communities):
        for node in comm:
            mapping[str(node)] = idx
    return mapping


def _split_oversized(
    G: nx.Graph,
    partition: dict[str, int],
    max_fraction: float = 0.25,
    resolution: float = 1.5,
) -> dict[str, int]:
    """Split communities that are too large (> max_fraction of total nodes)."""
    total = len(partition)
    threshold = max(int(total * max_fraction), 10)

    # Group nodes by community
    communities: dict[int, list[str]] = {}
    for node, comm in partition.items():
        communities.setdefault(comm, []).append(node)

    next_id = max(partition.values()) + 1 if partition else 0
    new_partition = dict(partition)

    for comm_id, members in communities.items():
        if len(members) <= threshold:
            continue

        # Create subgraph and re-cluster at higher resolution
        subgraph = G.subgraph(members)
        try:
            sub_comms = nx.community.louvain_communities(
                subgraph, resolution=resolution, seed=42
            )
            if len(sub_comms) > 1:
                for sub_comm in sub_comms:
                    for node in sub_comm:
                        new_partition[str(node)] = next_id
                    next_id += 1
        except Exception:
            pass

    return new_partition


def cluster(
    G: nx.Graph,
    resolution: float = 1.0,
    method: str = "auto",
    hierarchical: bool = True,
    max_community_fraction: float = 0.25,
) -> dict[str, Any]:
    """Detect communities in the graph.

    Args:
        G: The knowledge graph.
        resolution: Clustering resolution (higher = more communities).
        method: "leiden", "louvain", or "auto" (try Leiden first).
        hierarchical: Whether to split oversized communities.
        max_community_fraction: Max fraction of nodes in one community before splitting.

    Returns:
        Dict with:
            - partition: {node_id: community_id}
            - communities: {community_id: [node_ids]}
            - method: which algorithm was used
            - stats: community size statistics
            - hierarchy: nested sub-community info (if hierarchical=True)
    """
    # Work on undirected copy for community detection
    if G.is_directed():
        H = G.to_undirected()
    else:
        H = G

    # Remove isolates for better clustering
    isolates = list(nx.isolates(H))
    H_connected = H.copy()
    H_connected.remove_nodes_from(isolates)

    if H_connected.number_of_nodes() < 2:
        partition = {n: 0 for n in G.nodes()}
        communities = {0: list(G.nodes())}
        return {
            "partition": partition,
            "communities": communities,
            "method": "trivial",
            "stats": _community_stats(communities),
            "hierarchy": {},
        }

    # Choose method
    used_method = method
    partition = None

    if method in ("auto", "leiden"):
        partition = _try_leiden(H_connected, resolution)
        if partition is not None:
            used_method = "leiden"

    if partition is None:
        partition = _louvain(H_connected, resolution)
        used_method = "louvain"

    # Add isolates to their own communities
    if isolates:
        max_comm = max(partition.values()) + 1 if partition else 0
        for i, node in enumerate(isolates):
            partition[str(node)] = max_comm + i

    # Split oversized communities
    if hierarchical:
        partition = _split_oversized(H, partition, max_community_fraction, resolution * 1.5)

    # Build community → members mapping
    communities: dict[int, list[str]] = {}
    for node, comm in partition.items():
        communities.setdefault(comm, []).append(node)

    # Sort communities by size (largest first)
    sorted_comms = sorted(communities.items(), key=lambda x: -len(x[1]))
    # Reassign IDs to be 0-indexed by size
    remap = {old_id: new_id for new_id, (old_id, _) in enumerate(sorted_comms)}
    partition = {node: remap[comm] for node, comm in partition.items()}
    communities = {remap[cid]: members for cid, members in communities.items()}

    # Assign community to graph nodes
    for node, comm_id in partition.items():
        if node in G:
            G.nodes[node]["community"] = comm_id

    # Build hierarchy info
    hierarchy = {}
    if hierarchical:
        hierarchy = _build_hierarchy(G, communities)

    return {
        "partition": partition,
        "communities": communities,
        "method": used_method,
        "stats": _community_stats(communities),
        "hierarchy": hierarchy,
    }


def _community_stats(communities: dict[int, list[str]]) -> dict:
    """Compute community size statistics."""
    sizes = [len(members) for members in communities.values()]
    if not sizes:
        return {"count": 0, "sizes": [], "avg_size": 0, "max_size": 0, "min_size": 0}

    return {
        "count": len(sizes),
        "sizes": sorted(sizes, reverse=True),
        "avg_size": round(sum(sizes) / len(sizes), 1),
        "max_size": max(sizes),
        "min_size": min(sizes),
    }


def _build_hierarchy(
    G: nx.Graph, communities: dict[int, list[str]]
) -> dict[int, dict]:
    """Compute inter-community relationships for hierarchy view."""
    hierarchy: dict[int, dict] = {}

    for cid, members in communities.items():
        member_set = set(members)
        # Count edges going to other communities
        outgoing: dict[int, int] = {}
        for node in members:
            if node not in G:
                continue
            for neighbor in G.neighbors(node):
                n_comm = G.nodes[neighbor].get("community")
                if n_comm is not None and n_comm != cid:
                    outgoing[n_comm] = outgoing.get(n_comm, 0) + 1

        # Compute internal density (cohesion)
        subgraph = G.subgraph(members)
        internal_edges = subgraph.number_of_edges()
        max_edges = len(members) * (len(members) - 1) / 2
        cohesion = internal_edges / max_edges if max_edges > 0 else 0.0

        # Dominant node kinds in this community
        kinds: dict[str, int] = {}
        for node in members:
            if node in G:
                k = G.nodes[node].get("kind", "unknown")
                kinds[k] = kinds.get(k, 0) + 1

        hierarchy[cid] = {
            "size": len(members),
            "cohesion": round(cohesion, 3),
            "outgoing_edges": outgoing,
            "dominant_kinds": kinds,
            "internal_edges": internal_edges,
        }

    return hierarchy

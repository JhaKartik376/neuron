"""MCP stdio server exposing graph query tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


def _load_graph(graph_path: str) -> nx.Graph:
    data = json.loads(Path(graph_path).read_text())
    return json_graph.node_link_graph(data)


def _find_nodes(G: nx.Graph, query: str, limit: int = 20) -> list[str]:
    """Keyword search across node labels, kinds, and files."""
    q = query.lower()
    scored: list[tuple[str, int]] = []
    for node, data in G.nodes(data=True):
        label = (data.get("label") or node).lower()
        kind = (data.get("kind") or "").lower()
        file = (data.get("file") or "").lower()

        score = 0
        if q == label:
            score = 100
        elif label.startswith(q):
            score = 80
        elif q in label:
            score = 60
        elif q in file:
            score = 40
        elif q in kind:
            score = 20

        if score > 0:
            scored.append((node, score))

    scored.sort(key=lambda x: -x[1])
    return [n for n, _ in scored[:limit]]


def query_graph(
    G: nx.Graph,
    query: str,
    depth: int = 2,
    max_tokens: int = 4000,
    traversal: str = "bfs",
) -> dict[str, Any]:
    """Query the graph starting from keyword-matched nodes.

    Traverses via BFS or DFS up to `depth` hops, returning
    a token-budgeted subgraph.
    """
    start_nodes = _find_nodes(G, query)
    if not start_nodes:
        return {"matches": 0, "nodes": [], "edges": [], "message": f"No nodes matching '{query}'"}

    visited: set[str] = set()
    result_nodes: list[dict] = []
    result_edges: list[dict] = []
    token_est = 0

    frontier = [(n, 0) for n in start_nodes[:5]]

    while frontier and token_est < max_tokens:
        if traversal == "dfs":
            current, d = frontier.pop()
        else:
            current, d = frontier.pop(0)

        if current in visited or d > depth:
            continue
        visited.add(current)

        data = dict(G.nodes[current])
        node_info = {
            "id": current,
            "label": data.get("label", current),
            "kind": data.get("kind"),
            "file": data.get("file"),
            "community": data.get("community"),
            "degree": G.degree(current),
        }
        if data.get("docstring"):
            node_info["docstring"] = data["docstring"][:200]
        if data.get("signature"):
            node_info["signature"] = data["signature"]

        result_nodes.append(node_info)
        token_est += len(json.dumps(node_info)) // 4

        for neighbor in G.neighbors(current):
            edge_data = G[current][neighbor]
            result_edges.append({
                "source": data.get("label", current),
                "target": G.nodes[neighbor].get("label", neighbor),
                "relation": edge_data.get("relation", "related"),
                "confidence": edge_data.get("confidence", "unknown"),
            })
            token_est += 30

            if neighbor not in visited:
                frontier.append((neighbor, d + 1))

    return {
        "matches": len(start_nodes),
        "nodes": result_nodes,
        "edges": result_edges,
        "traversal": traversal,
        "depth": depth,
        "token_estimate": token_est,
    }


def get_node(G: nx.Graph, name: str) -> dict[str, Any] | None:
    """Get full details for a node."""
    matches = _find_nodes(G, name, limit=1)
    if not matches:
        return None
    node = matches[0]
    data = dict(G.nodes[node])
    data["id"] = node
    data["degree"] = G.degree(node)
    data["neighbors"] = [
        {
            "id": n,
            "label": G.nodes[n].get("label", n),
            "relation": G[node][n].get("relation", "related"),
        }
        for n in G.neighbors(node)
    ]
    return data


def get_neighbors(G: nx.Graph, name: str, relation_filter: str | None = None) -> list[dict]:
    """Get all neighbors of a node with edge details."""
    matches = _find_nodes(G, name, limit=1)
    if not matches:
        return []
    node = matches[0]
    result = []
    for n in G.neighbors(node):
        edge = G[node][n]
        rel = edge.get("relation", "related")
        if relation_filter and relation_filter not in rel:
            continue
        result.append({
            "id": n,
            "label": G.nodes[n].get("label", n),
            "kind": G.nodes[n].get("kind"),
            "relation": rel,
            "confidence": edge.get("confidence"),
        })
    return result


def get_community(G: nx.Graph, community_id: int) -> list[dict]:
    """Get all nodes in a community."""
    return [
        {
            "id": n,
            "label": data.get("label", n),
            "kind": data.get("kind"),
            "degree": G.degree(n),
        }
        for n, data in G.nodes(data=True)
        if data.get("community") == community_id
    ]


def god_nodes(G: nx.Graph, top_n: int = 10) -> list[dict]:
    """Get most connected nodes."""
    nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:top_n]
    return [
        {
            "id": n,
            "label": G.nodes[n].get("label", n),
            "kind": G.nodes[n].get("kind"),
            "degree": G.degree(n),
            "community": G.nodes[n].get("community"),
        }
        for n in nodes
    ]


def shortest_path(G: nx.Graph, source: str, target: str) -> dict[str, Any] | None:
    """Find shortest path between two concepts."""
    src_matches = _find_nodes(G, source, limit=1)
    tgt_matches = _find_nodes(G, target, limit=1)
    if not src_matches or not tgt_matches:
        return None

    src, tgt = src_matches[0], tgt_matches[0]
    try:
        path = nx.shortest_path(G, src, tgt)
    except nx.NetworkXNoPath:
        return {"source": source, "target": target, "path": None, "message": "No path found"}

    path_info = []
    for i, node in enumerate(path):
        info = {"id": node, "label": G.nodes[node].get("label", node), "kind": G.nodes[node].get("kind")}
        if i < len(path) - 1:
            edge = G[path[i]][path[i + 1]]
            info["edge_to_next"] = edge.get("relation", "related")
        path_info.append(info)

    return {"source": source, "target": target, "path": path_info, "length": len(path) - 1}


def run_mcp_server(graph_path: str):
    """Run the MCP stdio server.

    Exposes tools: query_graph, get_node, get_neighbors, get_community,
    god_nodes, graph_stats, shortest_path, health_check.
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp import types
    except ImportError:
        raise ImportError("Install MCP support: pip install neuron-graph[mcp]")

    G = _load_graph(graph_path)
    server = Server("neuron")

    @server.list_tools()
    async def list_tools():
        return [
            types.Tool(name="query_graph", description="Search and traverse the knowledge graph",
                      inputSchema={"type": "object", "properties": {
                          "query": {"type": "string"}, "depth": {"type": "integer", "default": 2},
                          "max_tokens": {"type": "integer", "default": 4000},
                      }, "required": ["query"]}),
            types.Tool(name="get_node", description="Get full details for a node",
                      inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
            types.Tool(name="get_neighbors", description="Get neighbors with edge details",
                      inputSchema={"type": "object", "properties": {
                          "name": {"type": "string"}, "relation": {"type": "string"},
                      }, "required": ["name"]}),
            types.Tool(name="get_community", description="Get all nodes in a community",
                      inputSchema={"type": "object", "properties": {"community_id": {"type": "integer"}}, "required": ["community_id"]}),
            types.Tool(name="god_nodes", description="Get most connected hub nodes",
                      inputSchema={"type": "object", "properties": {"top_n": {"type": "integer", "default": 10}}}),
            types.Tool(name="shortest_path", description="Find shortest path between concepts",
                      inputSchema={"type": "object", "properties": {
                          "source": {"type": "string"}, "target": {"type": "string"},
                      }, "required": ["source", "target"]}),
            types.Tool(name="graph_stats", description="Get graph statistics and health overview",
                      inputSchema={"type": "object", "properties": {}}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        import json as _json
        from .build import graph_stats as _graph_stats

        handlers = {
            "query_graph": lambda: query_graph(G, **arguments),
            "get_node": lambda: get_node(G, arguments["name"]),
            "get_neighbors": lambda: get_neighbors(G, arguments["name"], arguments.get("relation")),
            "get_community": lambda: get_community(G, arguments["community_id"]),
            "god_nodes": lambda: god_nodes(G, arguments.get("top_n", 10)),
            "shortest_path": lambda: shortest_path(G, arguments["source"], arguments["target"]),
            "graph_stats": lambda: _graph_stats(G),
        }

        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        result = handler()
        return [types.TextContent(type="text", text=_json.dumps(result, indent=2, default=str))]

    import asyncio
    async def _run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())

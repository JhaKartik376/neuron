"""Export graph to HTML (D3.js), JSON, SVG, Obsidian vault, GraphML, Neo4j."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


# ── JSON Export ──────────────────────────────────────────────────────

def export_json(G: nx.Graph, output_path: str | Path) -> Path:
    """Export graph as node-link JSON (NetworkX format)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json_graph.node_link_data(G)
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


# ── HTML Export (D3.js force-directed) ───────────────────────────────

_D3_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Neuron — Knowledge Graph</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; overflow: hidden; }
#container { display: flex; height: 100vh; }
#sidebar { width: 320px; background: #161b22; border-right: 1px solid #30363d; padding: 16px; overflow-y: auto; flex-shrink: 0; }
#graph { flex: 1; position: relative; }
svg { width: 100%; height: 100%; }
h1 { font-size: 18px; color: #58a6ff; margin-bottom: 12px; }
h2 { font-size: 14px; color: #8b949e; margin: 12px 0 6px; text-transform: uppercase; letter-spacing: 1px; }
input { width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; margin-bottom: 12px; }
input:focus { outline: none; border-color: #58a6ff; }
.stat { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; border-bottom: 1px solid #21262d; }
.stat-val { color: #58a6ff; font-weight: 600; }
#inspector { margin-top: 16px; }
.insp-label { font-size: 11px; color: #8b949e; text-transform: uppercase; }
.insp-value { font-size: 13px; margin-bottom: 8px; word-break: break-all; }
.legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; cursor: pointer; padding: 2px 8px; border-radius: 12px; border: 1px solid #30363d; }
.legend-item:hover { border-color: #58a6ff; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.health-badge { display: inline-block; padding: 4px 12px; border-radius: 6px; font-weight: 700; font-size: 24px; margin: 8px 0; }
.tooltip { position: absolute; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px; font-size: 12px; pointer-events: none; z-index: 100; max-width: 300px; }
link { stroke-opacity: 0.4; }
</style>
</head>
<body>
<div id="container">
  <div id="sidebar">
    <h1>Neuron</h1>
    <input type="text" id="search" placeholder="Search nodes..." />
    <div id="stats"></div>
    <h2>Health</h2>
    <div id="health"></div>
    <h2>Communities</h2>
    <div class="legend" id="legend"></div>
    <div id="inspector">
      <h2>Inspector</h2>
      <p style="font-size: 12px; color: #484f58;">Click a node to inspect</p>
    </div>
  </div>
  <div id="graph">
    <svg></svg>
    <div class="tooltip" id="tooltip" style="display:none;"></div>
  </div>
</div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const graphData = __GRAPH_DATA__;
const healthData = __HEALTH_DATA__;

const COLORS = [
  '#58a6ff','#f78166','#7ee787','#d2a8ff','#ffa657',
  '#79c0ff','#ff7b72','#56d364','#bc8cff','#e3b341',
  '#a5d6ff','#ffa198','#aff5b4','#cabffd','#f8e3a1',
];

const svg = d3.select('svg');
const width = document.getElementById('graph').clientWidth;
const height = document.getElementById('graph').clientHeight;
svg.attr('viewBox', [0, 0, width, height]);

const g = svg.append('g');

// Zoom
svg.call(d3.zoom().scaleExtent([0.1, 8]).on('zoom', (e) => {
  g.attr('transform', e.transform);
}));

const nodes = graphData.nodes.map(n => ({...n, id: n.id}));
const links = graphData.links.map(l => ({...l, source: l.source, target: l.target}));

// Degree for sizing
const degreeMap = {};
links.forEach(l => {
  degreeMap[l.source] = (degreeMap[l.source] || 0) + 1;
  degreeMap[l.target] = (degreeMap[l.target] || 0) + 1;
});

const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d => d.id).distance(80))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(d => nodeSize(d) + 4));

const link = g.append('g')
  .selectAll('line')
  .data(links)
  .join('line')
  .attr('stroke', '#30363d')
  .attr('stroke-width', d => d.confidence === 'extracted' ? 1.5 : 0.8)
  .attr('stroke-dasharray', d => d.confidence === 'inferred' ? '4,3' : d.confidence === 'ambiguous' ? '2,2' : null);

const node = g.append('g')
  .selectAll('circle')
  .data(nodes)
  .join('circle')
  .attr('r', d => nodeSize(d))
  .attr('fill', d => COLORS[(d.community || 0) % COLORS.length])
  .attr('stroke', '#0d1117')
  .attr('stroke-width', 1.5)
  .attr('cursor', 'pointer')
  .call(drag(simulation));

const label = g.append('g')
  .selectAll('text')
  .data(nodes.filter(d => (degreeMap[d.id] || 0) >= 3))
  .join('text')
  .text(d => d.label || d.id)
  .attr('font-size', 10)
  .attr('fill', '#8b949e')
  .attr('text-anchor', 'middle')
  .attr('dy', d => -nodeSize(d) - 4);

function nodeSize(d) {
  return Math.min(3 + Math.sqrt(degreeMap[d.id] || 1) * 3, 20);
}

simulation.on('tick', () => {
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('cx', d => d.x).attr('cy', d => d.y);
  label.attr('x', d => d.x).attr('y', d => d.y);
});

// Tooltip
const tooltip = d3.select('#tooltip');
node.on('mouseover', (e, d) => {
  tooltip.style('display', 'block')
    .html(`<strong>${d.label || d.id}</strong><br>${d.kind || ''}<br>degree: ${degreeMap[d.id] || 0}`)
    .style('left', (e.offsetX + 12) + 'px')
    .style('top', (e.offsetY - 8) + 'px');
}).on('mouseout', () => tooltip.style('display', 'none'));

// Click to inspect
node.on('click', (e, d) => {
  const el = document.getElementById('inspector');
  el.innerHTML = `<h2>Inspector</h2>
    <div class="insp-label">Name</div><div class="insp-value">${d.label || d.id}</div>
    <div class="insp-label">Kind</div><div class="insp-value">${d.kind || 'unknown'}</div>
    <div class="insp-label">File</div><div class="insp-value">${d.file || 'N/A'}</div>
    <div class="insp-label">Community</div><div class="insp-value">${d.community ?? 'N/A'}</div>
    <div class="insp-label">Degree</div><div class="insp-value">${degreeMap[d.id] || 0}</div>
    ${d.docstring ? '<div class="insp-label">Docstring</div><div class="insp-value">' + d.docstring.slice(0,200) + '</div>' : ''}
    ${d.signature ? '<div class="insp-label">Signature</div><div class="insp-value">' + d.signature + '</div>' : ''}`;
});

// Search
document.getElementById('search').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  node.attr('opacity', d => !q || (d.label || d.id).toLowerCase().includes(q) ? 1 : 0.1);
  link.attr('opacity', d => {
    if (!q) return 1;
    const s = (d.source.label || d.source.id || '').toLowerCase();
    const t = (d.target.label || d.target.id || '').toLowerCase();
    return s.includes(q) || t.includes(q) ? 1 : 0.05;
  });
  label.attr('opacity', d => !q || (d.label || d.id).toLowerCase().includes(q) ? 1 : 0.1);
});

// Stats
const statsEl = document.getElementById('stats');
statsEl.innerHTML = `
  <div class="stat"><span>Nodes</span><span class="stat-val">${nodes.length}</span></div>
  <div class="stat"><span>Edges</span><span class="stat-val">${links.length}</span></div>
  <div class="stat"><span>Communities</span><span class="stat-val">${new Set(nodes.map(n => n.community)).size}</span></div>`;

// Health
const healthEl = document.getElementById('health');
if (healthData) {
  const gradeColors = {A:'#56d364',B:'#7ee787',C:'#e3b341',D:'#ffa657',F:'#ff7b72'};
  healthEl.innerHTML = `<div class="health-badge" style="background:${gradeColors[healthData.grade] || '#484f58'}20;color:${gradeColors[healthData.grade] || '#c9d1d9'}">${healthData.grade}</div>
    <div class="stat"><span>Score</span><span class="stat-val">${(healthData.overall_score * 100).toFixed(0)}%</span></div>`;
}

// Legend
const communities = [...new Set(nodes.map(n => n.community))].sort((a,b) => a-b);
const legendEl = document.getElementById('legend');
communities.forEach(c => {
  const item = document.createElement('div');
  item.className = 'legend-item';
  item.innerHTML = `<span class="legend-dot" style="background:${COLORS[c % COLORS.length]}"></span>${c}`;
  item.onclick = () => {
    const active = item.classList.toggle('active');
    node.attr('opacity', d => !active || d.community === c ? 1 : 0.15);
    link.attr('opacity', !active ? 1 : 0.05);
    label.attr('opacity', d => !active || d.community === c ? 1 : 0.1);
  };
  legendEl.appendChild(item);
});

function drag(sim) {
  return d3.drag()
    .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
}
</script>
</body>
</html>"""


def export_html(
    G: nx.Graph,
    output_path: str | Path,
    health_data: dict | None = None,
) -> Path:
    """Export interactive D3.js force-directed graph visualization."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    graph_data = json_graph.node_link_data(G)
    health_json = json.dumps(health_data or {}, default=str)
    graph_json = json.dumps(graph_data, default=str)

    html = _D3_TEMPLATE.replace("__GRAPH_DATA__", graph_json)
    html = html.replace("__HEALTH_DATA__", health_json)

    path.write_text(html)
    return path


# ── GraphML Export ───────────────────────────────────────────────────

def export_graphml(G: nx.Graph, output_path: str | Path) -> Path:
    """Export as GraphML for Gephi/yEd."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # GraphML doesn't support dict/list attributes — flatten them
    H = G.copy()
    for node in H.nodes():
        data = H.nodes[node]
        for k, v in list(data.items()):
            if isinstance(v, (dict, list)):
                data[k] = json.dumps(v, default=str)
            elif v is None:
                data[k] = ""

    for u, v in H.edges():
        data = H[u][v]
        for k, val in list(data.items()):
            if isinstance(val, (dict, list)):
                data[k] = json.dumps(val, default=str)
            elif val is None:
                data[k] = ""

    nx.write_graphml(H, str(path))
    return path


# ── Obsidian Vault Export ────────────────────────────────────────────

def export_obsidian(
    G: nx.Graph,
    output_dir: str | Path,
    cluster_info: dict | None = None,
) -> Path:
    """Export graph as an Obsidian vault with wikilinks."""
    out = Path(output_dir) / "obsidian-vault"
    out.mkdir(parents=True, exist_ok=True)

    # Write one .md per node
    for node, data in G.nodes(data=True):
        label = data.get("label", node)
        safe_name = label.replace("/", "_").replace("\\", "_").replace(":", "_")
        filepath = out / f"{safe_name}.md"

        lines = [f"# {label}\n"]
        lines.append(f"**Kind:** {data.get('kind', 'unknown')}")
        if data.get("file"):
            lines.append(f"**File:** `{data['file']}`")
        if data.get("community") is not None:
            lines.append(f"**Community:** {data['community']}")
        if data.get("docstring"):
            lines.append(f"\n> {data['docstring'][:300]}")
        if data.get("signature"):
            lines.append(f"\n```\n{data['signature']}\n```")

        # Connections
        neighbors = list(G.neighbors(node))
        if neighbors:
            lines.append("\n## Connections\n")
            for n in neighbors:
                n_label = G.nodes[n].get("label", n)
                safe_n = n_label.replace("/", "_").replace("\\", "_").replace(":", "_")
                edge = G[node][n]
                rel = edge.get("relation", "related")
                lines.append(f"- [[{safe_n}]] ({rel})")

        filepath.write_text("\n".join(lines))

    # Write community overview notes
    if cluster_info and "communities" in cluster_info:
        for cid, members in cluster_info["communities"].items():
            filepath = out / f"_Community_{cid}.md"
            lines = [f"# Community {cid}\n"]
            lines.append(f"**Size:** {len(members)} nodes\n")
            for m in members:
                label = G.nodes[m].get("label", m) if m in G else m
                safe = label.replace("/", "_").replace("\\", "_").replace(":", "_")
                lines.append(f"- [[{safe}]]")
            filepath.write_text("\n".join(lines))

    return out


# ── SVG Export ───────────────────────────────────────────────────────

def export_svg(G: nx.Graph, output_path: str | Path) -> Path:
    """Export static SVG using matplotlib + NetworkX layout."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("Install matplotlib for SVG export: pip install neuron-graph[svg]")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    pos = nx.spring_layout(G, k=2 / max(G.number_of_nodes() ** 0.5, 1), seed=42)

    # Color by community
    communities = [G.nodes[n].get("community", 0) for n in G.nodes()]
    colors = ["#58a6ff", "#f78166", "#7ee787", "#d2a8ff", "#ffa657",
              "#79c0ff", "#ff7b72", "#56d364", "#bc8cff", "#e3b341"]
    node_colors = [colors[c % len(colors)] for c in communities]

    # Size by degree
    degrees = [max(G.degree(n) * 30, 50) for n in G.nodes()]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#30363d", alpha=0.3, width=0.5)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=degrees, alpha=0.9)

    # Label high-degree nodes
    labels = {
        n: G.nodes[n].get("label", n)
        for n in G.nodes()
        if G.degree(n) >= 3
    }
    nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=7, font_color="#c9d1d9")

    ax.set_axis_off()
    fig.savefig(str(path), format="svg", bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    return path


# ── Neo4j Export ─────────────────────────────────────────────────────

def export_cypher(G: nx.Graph, output_path: str | Path) -> Path:
    """Export as Cypher statements for Neo4j import."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["// Generated by Neuron\n"]

    # Nodes
    for node, data in G.nodes(data=True):
        label = (data.get("label", node) or node).replace("'", "\\'")
        kind = data.get("kind", "Entity")
        props = {
            "name": label,
            "kind": kind,
            "file": data.get("file", ""),
            "community": data.get("community", -1),
        }
        prop_str = ", ".join(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}" for k, v in props.items())
        lines.append(f"CREATE (:{kind.capitalize()} {{{prop_str}}});")

    lines.append("")

    # Edges
    for u, v, data in G.edges(data=True):
        u_label = (G.nodes[u].get("label", u) or u).replace("'", "\\'")
        v_label = (G.nodes[v].get("label", v) or v).replace("'", "\\'")
        rel = data.get("relation", "RELATED").upper().replace(",", "_")
        conf = data.get("confidence", "unknown")
        lines.append(
            f'MATCH (a {{name: "{u_label}"}}), (b {{name: "{v_label}"}}) '
            f'CREATE (a)-[:{rel} {{confidence: "{conf}"}}]->(b);'
        )

    path.write_text("\n".join(lines))
    return path


# ── Convenience: export all ──────────────────────────────────────────

def export_all(
    G: nx.Graph,
    output_dir: str | Path,
    health_data: dict | None = None,
    cluster_info: dict | None = None,
    formats: set[str] | None = None,
) -> dict[str, Path]:
    """Export graph in all (or selected) formats.

    Args:
        formats: Set of format names to export. None = all.
                 Options: json, html, graphml, obsidian, svg, cypher

    Returns:
        Dict mapping format name to output file path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    formats = formats or {"json", "html", "graphml", "obsidian", "cypher"}
    paths: dict[str, Path] = {}

    if "json" in formats:
        paths["json"] = export_json(G, out / "graph.json")
    if "html" in formats:
        paths["html"] = export_html(G, out / "graph.html", health_data)
    if "graphml" in formats:
        paths["graphml"] = export_graphml(G, out / "graph.graphml")
    if "obsidian" in formats:
        paths["obsidian"] = export_obsidian(G, out, cluster_info)
    if "svg" in formats:
        try:
            paths["svg"] = export_svg(G, out / "graph.svg")
        except ImportError:
            pass
    if "cypher" in formats:
        paths["cypher"] = export_cypher(G, out / "cypher.txt")

    return paths

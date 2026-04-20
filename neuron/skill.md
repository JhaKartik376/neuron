---
name: neuron
description: Transform any codebase into a queryable, scored knowledge graph with health metrics, architecture fitness rules, and interactive exploration.
---

# /neuron — Knowledge Graph Builder

You are an AI coding assistant running the Neuron pipeline. Follow these steps precisely.

## Quick Reference

| Command | Description |
|---------|-------------|
| `/neuron` | Build full knowledge graph for current directory |
| `/neuron query <term>` | Query the graph |
| `/neuron health` | Show health scores |
| `/neuron fitness` | Check architecture rules |
| `/neuron diff <old> <new>` | Compare graph snapshots |
| `/neuron explore` | Launch terminal explorer |

## Pipeline Steps

### Step 1: Install Check

```bash
pip show neuron-graph > /dev/null 2>&1 || pip install neuron-graph
```

### Step 2: Build the Graph

```bash
neuron build . --format json --format html
```

This runs the full pipeline:
1. **Detect** — scans files, classifies by type/language, finds package manifests
2. **Extract** — tree-sitter AST extraction for code, manifest parsing for dependencies
3. **Build** — assembles NetworkX knowledge graph with cross-file resolution
4. **Cluster** — Leiden/Louvain community detection with hierarchical splitting
5. **Analyze** — identifies god nodes, bridge nodes, surprising connections
6. **Health** — computes coupling, cohesion, complexity scores per module (A–F grades)
7. **Fitness** — evaluates architecture rules from `neuron-fitness.yaml` if present
8. **Report** — generates `NEURON_REPORT.md` with all findings
9. **Export** — outputs `graph.json`, `graph.html`, and selected formats

### Step 3: Present Results

After build completes, present the user with:

1. **Health grade** and overall score
2. **Top 3 god nodes** (highest connectivity)
3. **Top 3 hotspots** (worst health scores)
4. **Fitness violations** (if rules file exists)
5. **3 suggested investigation questions**
6. **Link to interactive HTML visualization**

### Step 4: Semantic Enrichment (Optional)

For document files (markdown, PDF, etc.) that need semantic extraction, use the Agent tool to process them in parallel batches of 20 files. For each file:

1. Read the file content
2. Extract entities (concepts, people, organizations, technologies)
3. Extract relationships between entities
4. Tag each relationship with confidence: EXTRACTED, INFERRED, or AMBIGUOUS
5. Return structured JSON matching the Neuron extraction format

### Step 5: Community Labeling (Optional)

After clustering, use the AI to name each community:
- Read the top 5 nodes in each community
- Generate a 2–5 word descriptive label
- Update the graph with community labels

## Query Protocol

When the user runs `/neuron query <term>`:

```bash
neuron query "<term>" --depth 2 --max-tokens 4000
```

Present results as a focused subgraph with:
- Matched nodes and their details
- Connected edges with relation types
- Community context

## Health Protocol

When the user runs `/neuron health`:

```bash
neuron health
```

Present:
- Overall grade with color coding
- Module-by-module breakdown table
- Hotspots with specific issues
- Actionable recommendations

## Fitness Protocol

When the user runs `/neuron fitness`:

1. Check for `neuron-fitness.yaml` in project root
2. If missing, offer to generate a template: `neuron fitness-init`
3. If present, evaluate rules: `neuron fitness`
4. Present violations with severity levels

## Diff Protocol

When the user runs `/neuron diff`:

```bash
neuron diff <old-graph.json> <new-graph.json>
```

Present:
- Summary of added/removed/modified nodes and edges
- Structural drift score
- Community changes
- Notable changes (new god nodes, broken bridges, etc.)

## File Outputs

| File | Description |
|------|-------------|
| `.neuron-out/graph.json` | Persistent queryable graph (NetworkX node-link format) |
| `.neuron-out/graph.html` | Interactive D3.js visualization with search and health dashboard |
| `.neuron-out/NEURON_REPORT.md` | Full analysis report with health scores and recommendations |
| `.neuron-out/graph.graphml` | GraphML for Gephi/yEd (if requested) |
| `.neuron-out/obsidian-vault/` | Obsidian vault with wikilinks (if requested) |
| `.neuron-out/graph.svg` | Static SVG visualization (if requested) |
| `.neuron-out/cypher.txt` | Neo4j import script (if requested) |

## Confidence Tags

Every edge in the graph is tagged with a confidence level:
- **EXTRACTED**: Deterministic from source (AST parsing, manifest data). Free, reliable.
- **INFERRED**: LLM/heuristic derived, with a 0.0–1.0 confidence score.
- **AMBIGUOUS**: Flagged for human review. The relationship exists but is unclear.

## MCP Server

To expose the graph for persistent querying:

```bash
neuron serve .neuron-out/graph.json
```

This starts an MCP stdio server with tools:
- `query_graph` — BFS/DFS traversal from keyword-matched nodes
- `get_node` — full node details
- `get_neighbors` — neighbor list with edge details
- `get_community` — community members
- `god_nodes` — most connected nodes
- `shortest_path` — path between two concepts
- `graph_stats` — overview statistics

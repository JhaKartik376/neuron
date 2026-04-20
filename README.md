# Neuron

**Transform any codebase into a queryable, scored knowledge graph — with health grades, architecture fitness rules, and interactive exploration.**

Neuron scans your project, parses every file using tree-sitter AST extraction, builds a knowledge graph of entities and relationships, clusters them into communities, scores each module's health from A to F, and gives you an interactive visualization to explore it all.

No embeddings. No API keys for code. Deterministic AST parsing. Your code never leaves your machine.

```
neuron build .
```

```
Scanning files...
  Found 26 files across 2 languages
Extracting entities...
  Extracted 266 entities, 1939 relations
Building knowledge graph...
  624 nodes, 1301 edges
Detecting communities...
  23 communities via louvain
Computing health scores...
  Overall health: B (82%)

╭─────────────── Neuron Summary ───────────────╮
│   Nodes           624                        │
│   Edges           1301                       │
│   Communities     23                         │
│   Health          B (82%)                    │
│   God Nodes       10                         │
│   Bridge Nodes    10                         │
╰──────────────────────────────────────────────╯
```

---

## Why Neuron?

You open a new codebase. Thousands of files. Who calls what? Which modules are tightly coupled? Where are the god objects hiding? What would break if you refactored that one service?

Neuron answers all of this in seconds.

| Problem | How Neuron Helps |
|---------|-----------------|
| "I don't understand this codebase" | Builds a full knowledge graph you can query and explore |
| "Which modules are the most fragile?" | Health scores with coupling, cohesion, and complexity grades |
| "Are we violating our architecture?" | Fitness rules catch layer violations, circular deps, and coupling limits |
| "What changed structurally?" | Graph diffing shows added/removed nodes, edges, and drift scores |
| "I need to present this to my team" | Interactive D3.js visualization, Obsidian vaults, SVG exports |

---

## Installation

```bash
pip install neuron-graph
```

Or from source:

```bash
git clone https://github.com/kartikjha/neuron.git
cd neuron
pip install -e ".[all]"
```

### Optional Extras

```bash
pip install neuron-graph[mcp]        # MCP server for AI assistants
pip install neuron-graph[tui]        # Textual-based terminal UI
pip install neuron-graph[svg]        # Static SVG export (matplotlib)
pip install neuron-graph[pdf]        # PDF document parsing
pip install neuron-graph[watch]      # File watcher with live reload
pip install neuron-graph[leiden]     # Leiden community detection
pip install neuron-graph[office]     # Word/Excel document parsing
pip install neuron-graph[video]      # Video/audio transcription
pip install neuron-graph[neo4j]      # Neo4j graph database export
pip install neuron-graph[embeddings] # Semantic similarity search
pip install neuron-graph[all]        # Everything
```

---

## Quick Start

### Build a knowledge graph

```bash
neuron build /path/to/your/project
```

This runs the full pipeline and outputs:

| File | What It Is |
|------|-----------|
| `.neuron-out/graph.html` | Interactive D3.js visualization |
| `.neuron-out/graph.json` | Queryable graph data (NetworkX format) |
| `.neuron-out/NEURON_REPORT.md` | Full analysis report with health scores |

### Query the graph

```bash
neuron query "UserService" --depth 3
```

```
┌─────────────────────────────────────────────┐
│ Results for 'UserService'                   │
├──────────────┬──────────┬──────┬────────────┤
│ Node         │ Kind     ��� File │ Degree     │
├──────────────┼──────────┼──────┼────────────┤
│ UserService  │ class    │ ...  │ 12         │
│ getUser      │ method   │ ...  │ 4          │
│ createUser   │ method   │ ...  │ 6          │
│ validate     │ method   │ ...  │ 3          │
│ UserRepo     │ class    │ ...  │ 8          │
└──────────────┴──────────┴──────┴────────────┘
```

### Check codebase health

```bash
neuron health
```

```
╭──── Codebase Health ────╮
│       B (82%)           │
╰─────────────────────────╯

┌──────────┬───────��──────────┬──────────┬────��───────┬───────┐
│ Module   │ Grade │ Coupling │ Cohesion │ Complexity │ Score │
├──────────┼───────┼──────────┼──────────┼────────────┼───────┤
│ auth     │ A     │ 0.95     │ 0.88     │ 0.92       │ 0.91  │
│ api      │ B     │ 0.78     │ 0.82     │ 0.85       │ 0.81  │
│ utils    │ D     │ 0.42     │ 0.31     │ 0.55       │ 0.43  ���
└──────────┴───────┴──────────┴──────────┴────────────┴───────┘

Recommendations:
  - Reduce coupling in [utils]: extract shared interfaces
  - Improve cohesion in [utils]: consider splitting this module
```

### Check architecture fitness

```bash
neuron fitness
```

Create a `neuron-fitness.yaml` in your project root:

```yaml
rules:
  - name: no-ui-to-db
    kind: no-depend
    description: UI layer must not directly access database
    source: "ui/*"
    target: "db/*"
    severity: error

  - name: max-service-coupling
    kind: max-coupling
    source: "services/*"
    threshold: 10
    severity: warning

  - name: layered-architecture
    kind: layer-order
    layers:
      - "controller"
      - "service"
      - "repository"
    severity: error

  - name: no-circular-deps
    kind: no-circular
    source: "services/*"
    severity: error
```

```
Fitness: FAIL (3/4 rules passed)

┌──────────┬─────────────────┬───────────────────────────────────────────┐
│ Severity │ Rule            │ Message                                   │
├──────────┼─────────────────┼───────────────────────────────────────────┤
│ error    │ no-ui-to-db     │ UIView must not depend on UserRepo        │
└──────────┴─────────────────┴───────────────────────────────────────────┘
```

### Compare graph snapshots

```bash
neuron diff old-graph.json new-graph.json
```

```
╭──────────────── Graph Diff ────────────���────╮
│ +12 nodes, -3 nodes, ~8 modified,           │
│ +18 edges, -5 edges, drift=6.42%            │
╰─────────────────────────────────────────────╯
```

### Explore interactively in the terminal

```bash
neuron explore
```

```
╭──── Neuron Graph Explorer ────╮
│ 624 nodes, 1301 edges         │
│ Type 'help' for commands       │
╰───────────────────────────────╯

neuron> search UserService
neuron> node UserService
neuron> neighbors UserService
neuron> path UserService → Database
neuron> tree UserService
neuron> gods
neuron> health
neuron> community 3
neuron> quit
```

### Watch for changes

```bash
neuron watch .
```

Auto-rebuilds the graph when files change.

### Start MCP server

```bash
neuron serve .neuron-out/graph.json
```

Exposes 7 tools to any MCP-compatible AI assistant (Claude Code, Cursor, etc.):

| Tool | What It Does |
|------|-------------|
| `query_graph` | BFS/DFS traversal from keyword-matched nodes |
| `get_node` | Full details for any node |
| `get_neighbors` | Direct neighbors with edge details |
| `get_community` | All nodes in a community |
| `god_nodes` | Most connected hub nodes |
| `shortest_path` | Path between two concepts |
| `graph_stats` | Node/edge counts, health overview |

---

## The Pipeline

```
detect → extract → build → cluster → analyze → health → fitness → report → export
```

Each stage is a pure function in its own module. No global state.

### 1. Detect

Walks your project directory. Classifies every file by type and language. Finds package manifests (`package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, etc.). Respects `.neuronignore`. Skips sensitive files (keys, credentials, `.env`).

### 2. Extract

Uses **tree-sitter** for deterministic AST extraction across languages. Zero API calls for code. Extracts:

- Functions, methods, classes, interfaces
- Import/export relationships
- Call graphs (cross-file)
- Inheritance and implementation chains
- Docstrings and signatures
- Visibility (public/private/protected)
- Dependencies from package manifests

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, and more.

### 3. Build

Merges all extraction results into a **NetworkX** graph. Resolves cross-file references (when `module_b` imports `ClassA` from `module_a`, those nodes get connected). Deduplicates entities. Tags external dependencies.

### 4. Cluster

Runs **Leiden** community detection (or falls back to **Louvain**). Automatically splits oversized communities. Builds a hierarchy of nested sub-communities with cohesion scores and inter-community relationship maps.

### 5. Analyze

Computes four centrality metrics for every node (degree, betweenness, eigenvector, closeness). Identifies:

- **God nodes** — entities with disproportionately high connectivity, with risk scores
- **Bridge nodes** — nodes that span multiple communities (potential architectural seams)
- **Surprising connections** — unexpected cross-community, cross-file edges ranked by composite surprise score
- **Suggested questions** — investigation prompts generated from structural analysis

### 6. Health Score

Computes **per-module health grades** (A through F) based on three dimensions:

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Coupling** | Afferent/efferent dependencies, instability ratio | High coupling = changes ripple everywhere |
| **Cohesion** | Internal connectivity density | Low cohesion = module is doing too many things |
| **Complexity** | God node count, max fan-out | High complexity = hard to understand and test |

Identifies **hotspots** (worst modules) and generates **actionable recommendations** for refactoring.

### 7. Fitness Rules

Evaluates your architecture constraints defined in `neuron-fitness.yaml`:

| Rule Kind | What It Enforces |
|-----------|-----------------|
| `no-depend` | A must NOT depend on B |
| `must-depend` | A MUST depend on B |
| `max-coupling` | Module can have at most N external deps |
| `max-fan-out` | Entity can have at most N outgoing edges |
| `max-fan-in` | Entity can have at most N incoming edges |
| `layer-order` | Enforce layered architecture direction |
| `no-circular` | No circular dependencies |
| `max-community-size` | Community cannot exceed N nodes |

### 8. Report

Generates `NEURON_REPORT.md` with everything: health dashboard, module scores table, hotspots, fitness violations, god nodes, bridge nodes, surprising connections, community breakdowns, recommendations, and suggested investigation questions.

### 9. Export

| Format | Library | Description |
|--------|---------|-------------|
| **HTML** | D3.js force-directed | Interactive visualization with search, inspector, community filtering, health dashboard |
| **JSON** | NetworkX node-link | Persistent queryable graph data |
| **GraphML** | — | For Gephi, yEd, and other graph tools |
| **Obsidian** | Wikilinks | One `.md` per node with `[[links]]`, community overview notes |
| **SVG** | matplotlib | Static publication-quality graph image |
| **Cypher** | — | Neo4j import script |

---

## Confidence Tags

Every edge in the graph is tagged:

| Tag | Meaning | Visual |
|-----|---------|--------|
| **EXTRACTED** | Deterministic from source code (AST, manifest) | Solid line |
| **INFERRED** | Heuristic/LLM derived, with 0.0–1.0 score | Dashed line |
| **AMBIGUOUS** | Flagged for human review | Dotted line |

---

## Use as an AI Skill

Neuron works as a `/neuron` slash command in AI coding assistants:

```
/neuron              Build full knowledge graph
/neuron query <x>    Query the graph
/neuron health       Show health scores
/neuron fitness      Check architecture rules
/neuron diff         Compare snapshots
/neuron explore      Terminal explorer
```

Works with Claude Code, Cursor, Codex, and any MCP-compatible tool.

---

## Configuration

### `.neuronignore`

Same syntax as `.gitignore`. Controls which files to skip:

```
# Skip generated code
*.generated.ts
proto/**

# Skip vendored deps
third_party/
```

### `neuron-fitness.yaml`

Architecture fitness rules. Generate a starter template:

```bash
neuron fitness-init
```

---

## Caching

Neuron caches extraction results using SHA256 file hashes. Re-runs only process files that changed. Cache is stored in `.neuron-out/.cache/`.

---

## How Is This Different?

Neuron is inspired by the knowledge graph approach but adds features that help you actually *improve* your codebase, not just visualize it:

| Feature | Description |
|---------|-------------|
| **Health Scoring** | Quantitative A–F grades per module with coupling, cohesion, and complexity metrics |
| **Fitness Rules** | YAML-based architecture constraints that catch violations automatically |
| **Graph Diffing** | Compare snapshots across branches/commits with structural drift scores |
| **Terminal Explorer** | Full REPL for navigating the graph without opening a browser |
| **Bridge Detection** | Finds nodes that span communities — natural refactoring seams |
| **Risk Scoring** | God nodes get risk scores based on betweenness centrality + degree |
| **Dependency Awareness** | Reads package manifests (npm, cargo, go, pip, etc.) not just source code |
| **D3.js Visualization** | Force-directed graph with health dashboard, community filtering, and dark theme |
| **Actionable Output** | Not just "here's your graph" — generates specific refactoring recommendations |

---

## Project Structure

```
neuron/
├── neuron/
│   ├── __init__.py        # Lazy imports
│   ├── __main__.py        # CLI (click)
│   ├── detect.py          # File discovery + classification
│   ├── extract.py         # Tree-sitter AST extraction
│   ├── build.py           # NetworkX graph assembly
│   ├── cluster.py         # Leiden/Louvain community detection
│   ├── analyze.py         # Centrality, god nodes, bridges
│   ├── health.py          # Module health scoring (A–F)
│   ├── fitness.py         # Architecture fitness rules
│   ├── diff.py            # Graph snapshot diffing
│   ├── report.py          # NEURON_REPORT.md generation
│   ├── export.py          # HTML, JSON, GraphML, Obsidian, SVG, Neo4j
│   ├── tui.py             # Terminal graph explorer
│   ├── serve.py           # MCP server (7 tools)
│   ├── cache.py           # SHA256 incremental cache
│   ├── watch.py           # File watcher + WebSocket live reload
│   ├── security.py        # Input validation, SSRF protection
│   └── skill.md           # AI assistant skill definition
├── tests/                 # 50 tests covering all modules
├── pyproject.toml
└── LICENSE
```

---

## License

MIT

---

Built by [Kartik Jha](https://github.com/kartikjha).

# Neuron

**Transform any codebase into a queryable, scored knowledge graph — with health grades, architecture fitness rules, and interactive exploration.**

Neuron scans your project, parses every file using tree-sitter AST extraction, builds a knowledge graph of entities and relationships, clusters them into communities, scores each module's health from A to F, and gives you an interactive visualization to explore it all.

> No embeddings. No API keys for code. Deterministic AST parsing. Your code never leaves your machine.

```bash
neuron build .
```

```
Scanning files...        Found 26 files across 2 languages
Extracting entities...   Extracted 266 entities, 1939 relations
Building graph...        624 nodes, 1301 edges
Detecting communities... 23 communities via louvain
Health scores...         Overall health: B (82%)
```

---

## Why Neuron?

```mermaid
graph LR
    A["I don't understand\nthis codebase"] -->|neuron build| B["Full knowledge graph\nyou can query & explore"]
    C["Which modules\nare fragile?"] -->|neuron health| D["A-F grades with\ncoupling, cohesion,\ncomplexity metrics"]
    E["Are we violating\nour architecture?"] -->|neuron fitness| F["Catches layer violations,\ncircular deps,\ncoupling limits"]
    G["What changed\nstructurally?"] -->|neuron diff| H["Added/removed nodes,\nedges, drift scores"]
    I["I need to present\nthis to my team"] -->|neuron export| J["D3.js visualization,\nObsidian vaults,\nSVG exports"]

    style A fill:#ff6b6b,stroke:#c0392b,color:#fff
    style C fill:#ff6b6b,stroke:#c0392b,color:#fff
    style E fill:#ff6b6b,stroke:#c0392b,color:#fff
    style G fill:#ff6b6b,stroke:#c0392b,color:#fff
    style I fill:#ff6b6b,stroke:#c0392b,color:#fff
    style B fill:#2ecc71,stroke:#27ae60,color:#fff
    style D fill:#2ecc71,stroke:#27ae60,color:#fff
    style F fill:#2ecc71,stroke:#27ae60,color:#fff
    style H fill:#2ecc71,stroke:#27ae60,color:#fff
    style J fill:#2ecc71,stroke:#27ae60,color:#fff
```

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

```mermaid
graph TD
    N["neuron-graph"] --> mcp["[mcp]\nMCP server for\nAI assistants"]
    N --> tui["[tui]\nTextual terminal UI"]
    N --> svg["[svg]\nStatic SVG export"]
    N --> pdf["[pdf]\nPDF document parsing"]
    N --> watch["[watch]\nFile watcher +\nlive reload"]
    N --> leiden["[leiden]\nLeiden community\ndetection"]
    N --> office["[office]\nWord/Excel parsing"]
    N --> video["[video]\nVideo/audio\ntranscription"]
    N --> neo4j["[neo4j]\nNeo4j graph\ndatabase export"]
    N --> emb["[embeddings]\nSemantic similarity\nsearch"]
    N --> all["[all]\nEverything"]

    style N fill:#3498db,stroke:#2980b9,color:#fff
    style all fill:#e74c3c,stroke:#c0392b,color:#fff
```

```bash
pip install neuron-graph[mcp]        # MCP server for AI assistants
pip install neuron-graph[all]        # Everything
```

---

## Quick Start

### Build a knowledge graph

```bash
neuron build /path/to/your/project
```

```mermaid
graph LR
    B["neuron build ."] --> O1[".neuron-out/graph.html\nInteractive D3.js\nvisualization"]
    B --> O2[".neuron-out/graph.json\nQueryable graph data\nNetworkX format"]
    B --> O3[".neuron-out/NEURON_REPORT.md\nFull analysis report\nwith health scores"]

    style B fill:#3498db,stroke:#2980b9,color:#fff
    style O1 fill:#1abc9c,stroke:#16a085,color:#fff
    style O2 fill:#f39c12,stroke:#e67e22,color:#fff
    style O3 fill:#9b59b6,stroke:#8e44ad,color:#fff
```

### Query the graph

```bash
neuron query "UserService" --depth 3
```

```mermaid
graph TD
    US["UserService\n(class, degree: 12)"] --> gU["getUser\n(method, degree: 4)"]
    US --> cU["createUser\n(method, degree: 6)"]
    US --> v["validate\n(method, degree: 3)"]
    US --> UR["UserRepo\n(class, degree: 8)"]

    style US fill:#e74c3c,stroke:#c0392b,color:#fff
    style gU fill:#3498db,stroke:#2980b9,color:#fff
    style cU fill:#3498db,stroke:#2980b9,color:#fff
    style v fill:#3498db,stroke:#2980b9,color:#fff
    style UR fill:#e74c3c,stroke:#c0392b,color:#fff
```

### Check codebase health

```bash
neuron health
```

```mermaid
block-beta
    columns 4
    block:header:4
        h["Codebase Health: B (82%)"]
    end
    m1["auth\nA (91%)"] m2["api\nB (81%)"] m3["core\nC (72%)"] m4["utils\nD (43%)"]

    style header fill:#2ecc71,stroke:#27ae60,color:#fff
    style m1 fill:#2ecc71,stroke:#27ae60,color:#fff
    style m2 fill:#27ae60,stroke:#1e8449,color:#fff
    style m3 fill:#f39c12,stroke:#e67e22,color:#fff
    style m4 fill:#e74c3c,stroke:#c0392b,color:#fff
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
    layers: [controller, service, repository]
    severity: error

  - name: no-circular-deps
    kind: no-circular
    source: "services/*"
    severity: error
```

```mermaid
graph TD
    subgraph "Fitness: FAIL (3/4 rules passed)"
        R1["no-circular-deps\nPASS"] --- R2["layered-architecture\nPASS"]
        R2 --- R3["max-coupling\nPASS"]
        R3 --- R4["no-ui-to-db\nFAIL\nUIView -> UserRepo"]
    end

    style R1 fill:#2ecc71,stroke:#27ae60,color:#fff
    style R2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style R3 fill:#2ecc71,stroke:#27ae60,color:#fff
    style R4 fill:#e74c3c,stroke:#c0392b,color:#fff
```

### Compare graph snapshots

```bash
neuron diff old-graph.json new-graph.json
```

```mermaid
graph LR
    OLD["old-graph.json\n612 nodes\n1283 edges"] --> DIFF{"neuron diff"}
    NEW["new-graph.json\n624 nodes\n1301 edges"] --> DIFF
    DIFF --> R["+12 nodes, -3 nodes\n~8 modified\n+18 edges, -5 edges\ndrift = 6.42%"]

    style OLD fill:#95a5a6,stroke:#7f8c8d,color:#fff
    style NEW fill:#3498db,stroke:#2980b9,color:#fff
    style DIFF fill:#f39c12,stroke:#e67e22,color:#fff
    style R fill:#9b59b6,stroke:#8e44ad,color:#fff
```

### Explore interactively in the terminal

```bash
neuron explore
```

```
neuron> search UserService
neuron> node UserService
neuron> neighbors UserService
neuron> path UserService -> Database
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

```mermaid
graph TD
    S["MCP Server"] --> T1["query_graph\nBFS/DFS traversal"]
    S --> T2["get_node\nFull node details"]
    S --> T3["get_neighbors\nDirect neighbors"]
    S --> T4["get_community\nCommunity nodes"]
    S --> T5["god_nodes\nHub nodes"]
    S --> T6["shortest_path\nPath between concepts"]
    S --> T7["graph_stats\nCounts + health overview"]

    style S fill:#3498db,stroke:#2980b9,color:#fff
    style T1 fill:#1abc9c,stroke:#16a085,color:#fff
    style T2 fill:#1abc9c,stroke:#16a085,color:#fff
    style T3 fill:#1abc9c,stroke:#16a085,color:#fff
    style T4 fill:#1abc9c,stroke:#16a085,color:#fff
    style T5 fill:#1abc9c,stroke:#16a085,color:#fff
    style T6 fill:#1abc9c,stroke:#16a085,color:#fff
    style T7 fill:#1abc9c,stroke:#16a085,color:#fff
```

Works with Claude Code, Cursor, Codex, and any MCP-compatible tool.

---

## The Pipeline

```mermaid
graph LR
    D["Detect\nFile discovery"] --> E["Extract\nAST parsing"]
    E --> B["Build\nGraph assembly"]
    B --> CL["Cluster\nCommunities"]
    CL --> A["Analyze\nCentrality"]
    A --> H["Health\nA-F scoring"]
    H --> F["Fitness\nRule checks"]
    F --> R["Report\nMarkdown"]
    R --> EX["Export\nHTML/JSON/..."]

    style D fill:#e74c3c,stroke:#c0392b,color:#fff
    style E fill:#e67e22,stroke:#d35400,color:#fff
    style B fill:#f39c12,stroke:#e67e22,color:#fff
    style CL fill:#2ecc71,stroke:#27ae60,color:#fff
    style A fill:#1abc9c,stroke:#16a085,color:#fff
    style H fill:#3498db,stroke:#2980b9,color:#fff
    style F fill:#9b59b6,stroke:#8e44ad,color:#fff
    style R fill:#34495e,stroke:#2c3e50,color:#fff
    style EX fill:#e91e63,stroke:#c2185b,color:#fff
```

Each stage is a pure function in its own module. No global state.

### 1. Detect

Walks your project directory. Classifies every file by type and language. Finds package manifests (`package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, etc.). Respects `.neuronignore`. Skips sensitive files (keys, credentials, `.env`).

### 2. Extract

Uses **tree-sitter** for deterministic AST extraction across languages. Zero API calls for code. Extracts:

```mermaid
mindmap
    root((Extract))
        Entities
            Functions
            Methods
            Classes
            Interfaces
        Relationships
            Import/Export
            Call graphs
            Inheritance
        Metadata
            Docstrings
            Signatures
            Visibility
        Dependencies
            Package manifests
```

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, and more.

### 3. Build

Merges all extraction results into a **NetworkX** graph. Resolves cross-file references (when `module_b` imports `ClassA` from `module_a`, those nodes get connected). Deduplicates entities. Tags external dependencies.

### 4. Cluster

Runs **Leiden** community detection (or falls back to **Louvain**). Automatically splits oversized communities. Builds a hierarchy of nested sub-communities with cohesion scores and inter-community relationship maps.

### 5. Analyze

Computes four centrality metrics for every node (degree, betweenness, eigenvector, closeness). Identifies:

- **God nodes** -- entities with disproportionately high connectivity, with risk scores
- **Bridge nodes** -- nodes that span multiple communities (potential architectural seams)
- **Surprising connections** -- unexpected cross-community, cross-file edges ranked by composite surprise score
- **Suggested questions** -- investigation prompts generated from structural analysis

### 6. Health Score

Computes **per-module health grades** (A through F) based on three dimensions:

```mermaid
graph TD
    HS["Health Score\n(A-F)"] --> CP["Coupling\nAfferent/efferent deps\ninstability ratio"]
    HS --> CO["Cohesion\nInternal connectivity\ndensity"]
    HS --> CX["Complexity\nGod node count\nmax fan-out"]

    CP --> W1["High coupling =\nchanges ripple everywhere"]
    CO --> W2["Low cohesion =\nmodule doing too many things"]
    CX --> W3["High complexity =\nhard to understand & test"]

    style HS fill:#3498db,stroke:#2980b9,color:#fff
    style CP fill:#e74c3c,stroke:#c0392b,color:#fff
    style CO fill:#f39c12,stroke:#e67e22,color:#fff
    style CX fill:#9b59b6,stroke:#8e44ad,color:#fff
    style W1 fill:#fadbd8,stroke:#e74c3c,color:#333
    style W2 fill:#fdebd0,stroke:#f39c12,color:#333
    style W3 fill:#e8daef,stroke:#9b59b6,color:#333
```

Identifies **hotspots** (worst modules) and generates **actionable recommendations** for refactoring.

### 7. Fitness Rules

Evaluates your architecture constraints defined in `neuron-fitness.yaml`:

```mermaid
graph LR
    subgraph "Fitness Rule Kinds"
        ND["no-depend\nA must NOT\ndepend on B"]
        MD["must-depend\nA MUST\ndepend on B"]
        MC["max-coupling\nMax N external deps"]
        MFO["max-fan-out\nMax N outgoing edges"]
        MFI["max-fan-in\nMax N incoming edges"]
        LO["layer-order\nEnforce layered\narchitecture"]
        NC["no-circular\nNo circular deps"]
        MCS["max-community-size\nCommunity <= N nodes"]
    end

    style ND fill:#e74c3c,stroke:#c0392b,color:#fff
    style MD fill:#2ecc71,stroke:#27ae60,color:#fff
    style MC fill:#f39c12,stroke:#e67e22,color:#fff
    style MFO fill:#3498db,stroke:#2980b9,color:#fff
    style MFI fill:#3498db,stroke:#2980b9,color:#fff
    style LO fill:#9b59b6,stroke:#8e44ad,color:#fff
    style NC fill:#e74c3c,stroke:#c0392b,color:#fff
    style MCS fill:#1abc9c,stroke:#16a085,color:#fff
```

### 8. Report

Generates `NEURON_REPORT.md` with everything: health dashboard, module scores, hotspots, fitness violations, god nodes, bridge nodes, surprising connections, community breakdowns, recommendations, and suggested investigation questions.

### 9. Export

```mermaid
graph TD
    EX["Export"] --> HTML["HTML\nD3.js force-directed\ninteractive visualization"]
    EX --> JSON["JSON\nNetworkX node-link\nqueryable graph data"]
    EX --> GML["GraphML\nGephi, yEd\ngraph tools"]
    EX --> OBS["Obsidian\nWikilinks vault\none .md per node"]
    EX --> SVG["SVG\nmatplotlib\npublication-quality"]
    EX --> CYP["Cypher\nNeo4j import script"]

    style EX fill:#3498db,stroke:#2980b9,color:#fff
    style HTML fill:#e74c3c,stroke:#c0392b,color:#fff
    style JSON fill:#f39c12,stroke:#e67e22,color:#fff
    style GML fill:#2ecc71,stroke:#27ae60,color:#fff
    style OBS fill:#9b59b6,stroke:#8e44ad,color:#fff
    style SVG fill:#1abc9c,stroke:#16a085,color:#fff
    style CYP fill:#34495e,stroke:#2c3e50,color:#fff
```

---

## Confidence Tags

Every edge in the graph is tagged with a confidence level:

```mermaid
graph LR
    E["Edge"] --> EXT["EXTRACTED\nDeterministic from\nsource code / AST"]
    E --> INF["INFERRED\nHeuristic/LLM derived\n0.0 - 1.0 score"]
    E --> AMB["AMBIGUOUS\nFlagged for\nhuman review"]

    EXT -.-|"solid line"| V1[" "]
    INF -.-|"dashed line"| V2[" "]
    AMB -.-|"dotted line"| V3[" "]

    style E fill:#3498db,stroke:#2980b9,color:#fff
    style EXT fill:#2ecc71,stroke:#27ae60,color:#fff
    style INF fill:#f39c12,stroke:#e67e22,color:#fff
    style AMB fill:#e74c3c,stroke:#c0392b,color:#fff
    style V1 fill:none,stroke:none
    style V2 fill:none,stroke:none
    style V3 fill:none,stroke:none
```

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

```mermaid
mindmap
    root((Neuron))
        Health Scoring
            A-F grades per module
            Coupling, cohesion, complexity
        Fitness Rules
            YAML-based constraints
            Auto-detect violations
        Graph Diffing
            Branch/commit comparison
            Structural drift scores
        Terminal Explorer
            Full REPL navigation
            No browser required
        Bridge Detection
            Cross-community nodes
            Natural refactoring seams
        Risk Scoring
            Betweenness centrality
            Degree-based risk
        Dependency Awareness
            npm, cargo, go, pip
            Source code + manifests
        D3.js Visualization
            Force-directed graph
            Health dashboard + dark theme
        Actionable Output
            Refactoring recommendations
            Not just visualization
```

---

## Project Structure

```mermaid
graph TD
    subgraph "neuron/"
        INIT["__init__.py\nLazy imports"]
        MAIN["__main__.py\nCLI (click)"]
        DET["detect.py\nFile discovery"]
        EXT["extract.py\nTree-sitter AST"]
        BLD["build.py\nNetworkX graph"]
        CLU["cluster.py\nLeiden/Louvain"]
        ANA["analyze.py\nCentrality, gods, bridges"]
        HLT["health.py\nA-F scoring"]
        FIT["fitness.py\nArchitecture rules"]
        DIF["diff.py\nSnapshot diffing"]
        RPT["report.py\nReport generation"]
        EXP["export.py\nHTML, JSON, GraphML, ..."]
        TUI["tui.py\nTerminal explorer"]
        SRV["serve.py\nMCP server"]
        CAC["cache.py\nSHA256 cache"]
        WAT["watch.py\nFile watcher"]
        SEC["security.py\nInput validation"]
    end

    MAIN --> DET --> EXT --> BLD --> CLU --> ANA --> HLT --> FIT --> RPT --> EXP

    style MAIN fill:#e74c3c,stroke:#c0392b,color:#fff
    style DET fill:#e67e22,stroke:#d35400,color:#fff
    style EXT fill:#f39c12,stroke:#e67e22,color:#fff
    style BLD fill:#f1c40f,stroke:#f39c12,color:#333
    style CLU fill:#2ecc71,stroke:#27ae60,color:#fff
    style ANA fill:#1abc9c,stroke:#16a085,color:#fff
    style HLT fill:#3498db,stroke:#2980b9,color:#fff
    style FIT fill:#9b59b6,stroke:#8e44ad,color:#fff
    style RPT fill:#34495e,stroke:#2c3e50,color:#fff
    style EXP fill:#e91e63,stroke:#c2185b,color:#fff
    style TUI fill:#607d8b,stroke:#455a64,color:#fff
    style SRV fill:#607d8b,stroke:#455a64,color:#fff
    style CAC fill:#607d8b,stroke:#455a64,color:#fff
    style WAT fill:#607d8b,stroke:#455a64,color:#fff
    style SEC fill:#607d8b,stroke:#455a64,color:#fff
    style INIT fill:#607d8b,stroke:#455a64,color:#fff
```

---

## License

MIT

---

Built by [Kartik Jha](https://github.com/kartikjha).

"""Terminal UI explorer for Neuron knowledge graphs using Rich."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

import networkx as nx
from networkx.readwrite import json_graph


class GraphExplorer:
    """Interactive terminal graph explorer using Rich.

    Provides a simple REPL for navigating the knowledge graph:
      - `search <term>` — find nodes
      - `node <name>` — inspect a node
      - `neighbors <name>` — list neighbors
      - `community <id>` — show community members
      - `gods` — show god nodes
      - `path <from> <to>` — shortest path
      - `health` — show health overview
      - `stats` — graph statistics
      - `quit` — exit
    """

    def __init__(self, graph_path: str | Path):
        self.console = Console()
        data = json.loads(Path(graph_path).read_text())
        self.G = json_graph.node_link_graph(data)
        self.console.print(
            Panel(
                f"[bold cyan]Neuron Graph Explorer[/]\n"
                f"{self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges\n"
                f"Type 'help' for commands",
                border_style="cyan",
            )
        )

    def run(self):
        """Start the interactive REPL."""
        while True:
            try:
                cmd = self.console.input("[bold cyan]neuron>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if command in ("quit", "exit", "q"):
                break
            elif command == "help":
                self._help()
            elif command == "search":
                self._search(arg)
            elif command in ("node", "inspect"):
                self._inspect_node(arg)
            elif command in ("neighbors", "n"):
                self._neighbors(arg)
            elif command in ("community", "comm"):
                self._community(arg)
            elif command == "gods":
                self._gods()
            elif command == "path":
                self._path(arg)
            elif command == "stats":
                self._stats()
            elif command == "health":
                self._health()
            elif command == "tree":
                self._tree(arg)
            else:
                self.console.print(f"[yellow]Unknown command: {command}. Type 'help'.[/]")

    def _help(self):
        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        table.add_row("search <term>", "Find nodes by name")
        table.add_row("node <name>", "Inspect a node's details")
        table.add_row("neighbors <name>", "List a node's connections")
        table.add_row("community <id>", "Show community members")
        table.add_row("gods", "Show most connected nodes")
        table.add_row("path <from> → <to>", "Find shortest path")
        table.add_row("tree <name>", "Show dependency tree")
        table.add_row("stats", "Graph statistics")
        table.add_row("health", "Health overview")
        table.add_row("quit", "Exit explorer")
        self.console.print(table)

    def _find_node(self, query: str) -> str | None:
        q = query.lower().strip()
        best = None
        best_score = 0
        for node, data in self.G.nodes(data=True):
            label = (data.get("label") or node).lower()
            if q == label:
                return node
            if label.startswith(q) and len(label) - len(q) < 10:
                score = 80
            elif q in label:
                score = 60
            else:
                continue
            if score > best_score:
                best_score = score
                best = node
        return best

    def _search(self, query: str):
        if not query:
            self.console.print("[yellow]Usage: search <term>[/]")
            return

        q = query.lower()
        results = []
        for node, data in self.G.nodes(data=True):
            label = (data.get("label") or node).lower()
            if q in label:
                results.append((node, data))

        if not results:
            self.console.print(f"[yellow]No nodes matching '{query}'[/]")
            return

        table = Table(title=f"Search: '{query}' ({len(results)} results)")
        table.add_column("Name", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("File", style="dim")
        table.add_column("Deg", justify="right")

        for node, data in results[:20]:
            table.add_row(
                data.get("label", node),
                data.get("kind", ""),
                data.get("file", ""),
                str(self.G.degree(node)),
            )
        self.console.print(table)

    def _inspect_node(self, name: str):
        if not name:
            self.console.print("[yellow]Usage: node <name>[/]")
            return

        node = self._find_node(name)
        if not node:
            self.console.print(f"[yellow]Node '{name}' not found[/]")
            return

        data = self.G.nodes[node]
        lines = [
            f"[bold]{data.get('label', node)}[/]",
            f"Kind: {data.get('kind', 'unknown')}",
            f"File: {data.get('file', 'N/A')}",
            f"Community: {data.get('community', 'N/A')}",
            f"Degree: {self.G.degree(node)}",
        ]
        if data.get("signature"):
            lines.append(f"Signature: {data['signature']}")
        if data.get("docstring"):
            lines.append(f"Docstring: {data['docstring'][:200]}")

        self.console.print(Panel("\n".join(lines), border_style="cyan"))

    def _neighbors(self, name: str):
        if not name:
            self.console.print("[yellow]Usage: neighbors <name>[/]")
            return

        node = self._find_node(name)
        if not node:
            self.console.print(f"[yellow]Node '{name}' not found[/]")
            return

        neighbors = list(self.G.neighbors(node))
        if not neighbors:
            self.console.print("[yellow]No neighbors[/]")
            return

        table = Table(title=f"Neighbors of {self.G.nodes[node].get('label', node)}")
        table.add_column("Name", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("Relation", style="magenta")
        table.add_column("Confidence", style="dim")

        for n in neighbors:
            edge = self.G[node][n]
            table.add_row(
                self.G.nodes[n].get("label", n),
                self.G.nodes[n].get("kind", ""),
                edge.get("relation", "related"),
                edge.get("confidence", ""),
            )
        self.console.print(table)

    def _community(self, arg: str):
        if not arg:
            # List all communities
            comms: dict[int, int] = {}
            for _, data in self.G.nodes(data=True):
                c = data.get("community")
                if c is not None:
                    comms[c] = comms.get(c, 0) + 1

            table = Table(title="Communities")
            table.add_column("ID", justify="right")
            table.add_column("Size", justify="right")
            for cid, size in sorted(comms.items()):
                table.add_row(str(cid), str(size))
            self.console.print(table)
            return

        try:
            cid = int(arg)
        except ValueError:
            self.console.print("[yellow]Usage: community <id>[/]")
            return

        members = [
            (n, data) for n, data in self.G.nodes(data=True)
            if data.get("community") == cid
        ]
        if not members:
            self.console.print(f"[yellow]Community {cid} not found[/]")
            return

        members.sort(key=lambda x: -self.G.degree(x[0]))
        table = Table(title=f"Community {cid} ({len(members)} nodes)")
        table.add_column("Name", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("Degree", justify="right")
        for node, data in members[:25]:
            table.add_row(data.get("label", node), data.get("kind", ""), str(self.G.degree(node)))
        self.console.print(table)

    def _gods(self):
        nodes = sorted(self.G.nodes(), key=lambda n: self.G.degree(n), reverse=True)[:10]
        table = Table(title="God Nodes (Top 10 by degree)")
        table.add_column("Name", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("Degree", justify="right", style="bold")
        table.add_column("Community", justify="right")

        for n in nodes:
            data = self.G.nodes[n]
            table.add_row(
                data.get("label", n), data.get("kind", ""),
                str(self.G.degree(n)), str(data.get("community", "")),
            )
        self.console.print(table)

    def _path(self, arg: str):
        # Parse "from → to" or "from to"
        for sep in ("→", "->", " to "):
            if sep in arg:
                parts = arg.split(sep, 1)
                break
        else:
            parts = arg.split(maxsplit=1)

        if len(parts) != 2:
            self.console.print("[yellow]Usage: path <from> → <to>[/]")
            return

        src = self._find_node(parts[0].strip())
        tgt = self._find_node(parts[1].strip())

        if not src:
            self.console.print(f"[yellow]Source '{parts[0].strip()}' not found[/]")
            return
        if not tgt:
            self.console.print(f"[yellow]Target '{parts[1].strip()}' not found[/]")
            return

        try:
            path = nx.shortest_path(self.G, src, tgt)
        except nx.NetworkXNoPath:
            self.console.print("[yellow]No path found[/]")
            return

        tree = Tree(f"[bold]{self.G.nodes[path[0]].get('label', path[0])}[/]")
        current = tree
        for i in range(1, len(path)):
            edge = self.G[path[i-1]][path[i]]
            rel = edge.get("relation", "→")
            label = self.G.nodes[path[i]].get("label", path[i])
            current = current.add(f"--[{rel}]--> [bold]{label}[/]")

        self.console.print(Panel(tree, title=f"Path (length={len(path)-1})", border_style="blue"))

    def _tree(self, name: str):
        if not name:
            self.console.print("[yellow]Usage: tree <name>[/]")
            return

        node = self._find_node(name)
        if not node:
            self.console.print(f"[yellow]Node '{name}' not found[/]")
            return

        label = self.G.nodes[node].get("label", node)
        tree = Tree(f"[bold cyan]{label}[/]")
        self._build_tree(node, tree, visited={node}, depth=0, max_depth=3)
        self.console.print(tree)

    def _build_tree(self, node: str, tree: Tree, visited: set, depth: int, max_depth: int):
        if depth >= max_depth:
            return
        for neighbor in self.G.neighbors(node):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            n_data = self.G.nodes[neighbor]
            edge = self.G[node][neighbor]
            label = n_data.get("label", neighbor)
            rel = edge.get("relation", "")
            branch = tree.add(f"[dim]{rel}[/] → {label} [green]({n_data.get('kind', '')})[/]")
            self._build_tree(neighbor, branch, visited, depth + 1, max_depth)

    def _stats(self):
        from .build import graph_stats
        stats = graph_stats(self.G)

        table = Table(title="Graph Statistics", show_header=False)
        table.add_column(style="dim")
        table.add_column(style="bold")
        table.add_row("Nodes", str(stats["nodes"]))
        table.add_row("Edges", str(stats["edges"]))
        table.add_row("Density", f"{stats['density']:.4f}")
        table.add_row("Components", str(stats["components"]))

        if stats.get("node_kinds"):
            for kind, count in sorted(stats["node_kinds"].items(), key=lambda x: -x[1]):
                table.add_row(f"  {kind}", str(count))

        self.console.print(table)

    def _health(self):
        from .health import compute_health
        report = compute_health(self.G)

        grade_colors = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}
        color = grade_colors.get(report.grade, "white")
        self.console.print(Panel(
            f"[bold {color}]{report.grade}[/] ({report.overall_score:.0%})",
            title="Health",
            border_style=color,
        ))

        if report.hotspots:
            for h in report.hotspots:
                self.console.print(f"  [red]![/] {h['module']}: {', '.join(h['issues'])}")

        if report.recommendations:
            self.console.print("\n[bold]Recommendations:[/]")
            for rec in report.recommendations:
                self.console.print(f"  {rec}")


def explore(graph_path: str | Path):
    """Launch the interactive TUI explorer."""
    explorer = GraphExplorer(graph_path)
    explorer.run()

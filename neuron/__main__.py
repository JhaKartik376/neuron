"""Neuron CLI — transform any codebase into a queryable, scored knowledge graph."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _run_pipeline(
    root: str,
    output_dir: str = ".neuron-out",
    directed: bool = False,
    resolution: float = 1.0,
    fitness_file: str | None = None,
    formats: set[str] | None = None,
    prune_external: bool = False,
) -> dict:
    """Run the full Neuron pipeline and return results."""
    from .analyze import analyze
    from .build import build_graph, graph_stats, prune_graph
    from .cache import ExtractionCache
    from .cluster import cluster
    from .detect import detect
    from .export import export_all
    from .extract import extract_file
    from .fitness import FitnessReport, evaluate, load_rules
    from .health import compute_health
    from .report import generate_report

    root_path = Path(root).resolve()
    out_path = root_path / output_dir

    # Phase 1: Detect
    console.print("[bold blue]Scanning files...[/]")
    detection = detect(root_path)
    summary = detection.summary()
    console.print(f"  Found {summary['total_files']} files across {len(summary['languages'])} languages")
    console.print(f"  Manifests: {summary['manifests']}, Skipped: {summary['skipped']}")

    if not detection.files and not detection.manifests:
        console.print("[yellow]No files found to analyze.[/]")
        return {"error": "no files"}

    # Phase 2: Extract (with cache)
    console.print("[bold blue]Extracting entities...[/]")
    cache = ExtractionCache(out_path / ".cache")
    all_files = detection.files + detection.manifests
    extractions = []
    cached_count = 0

    for f in all_files:
        fhash = cache.file_hash(f.path)
        cached = cache.get(f.relative, fhash)
        if cached:
            from .extract import ExtractionResult, Entity, Relation, Confidence
            # Reconstruct from cached dict
            ext = ExtractionResult(
                file=cached["file"],
                file_hash=cached["file_hash"],
                language=cached["language"],
            )
            for e in cached.get("entities", []):
                ext.entities.append(Entity(**{k: v for k, v in e.items() if k != "metadata" or v}))
            for r in cached.get("relations", []):
                r_copy = dict(r)
                r_copy["confidence"] = Confidence(r_copy.get("confidence", "extracted"))
                r_copy.pop("metadata", None)
                ext.relations.append(Relation(**r_copy))
            extractions.append(ext)
            cached_count += 1
        else:
            ext = extract_file(f)
            extractions.append(ext)
            cache.put(f.relative, fhash, ext.to_dict())

    cache.save()
    total_entities = sum(len(e.entities) for e in extractions)
    total_relations = sum(len(e.relations) for e in extractions)
    console.print(f"  Extracted {total_entities} entities, {total_relations} relations")
    if cached_count:
        console.print(f"  ({cached_count} files from cache)")

    # Phase 3: Build graph
    console.print("[bold blue]Building knowledge graph...[/]")
    G = build_graph(extractions, directed=directed)
    if prune_external:
        G = prune_graph(G, remove_external=True)
    stats = graph_stats(G)
    console.print(f"  {stats['nodes']} nodes, {stats['edges']} edges, density={stats['density']:.4f}")

    # Phase 4: Cluster
    console.print("[bold blue]Detecting communities...[/]")
    cluster_info = cluster(G, resolution=resolution, hierarchical=True)
    console.print(f"  {cluster_info['stats']['count']} communities via {cluster_info['method']}")

    # Phase 5: Analyze
    console.print("[bold blue]Analyzing graph...[/]")
    analysis = analyze(G)
    console.print(f"  {len(analysis.god_nodes)} god nodes, {len(analysis.surprising_connections)} surprising connections")
    console.print(f"  {len(analysis.bridge_nodes)} bridge nodes")

    # Phase 6: Health scoring
    console.print("[bold blue]Computing health scores...[/]")
    health = compute_health(G)
    console.print(f"  Overall health: [bold]{health.grade}[/] ({health.overall_score:.0%})")
    if health.hotspots:
        console.print(f"  Hotspots: {', '.join(h['module'] for h in health.hotspots)}")

    # Phase 7: Fitness rules
    fitness: FitnessReport | None = None
    if fitness_file:
        rules_path = Path(fitness_file)
    else:
        rules_path = root_path / "neuron-fitness.yaml"

    if rules_path.is_file():
        console.print("[bold blue]Checking fitness rules...[/]")
        rules = load_rules(rules_path)
        fitness = evaluate(G, rules)
        console.print(f"  {fitness.passed}/{fitness.rules_checked} rules passed")
        if fitness.violations:
            for v in fitness.violations[:5]:
                icon = "[red]!![/]" if v.severity == "error" else "[yellow]?[/]"
                console.print(f"  {icon} {v.rule}: {v.message}")

    # Phase 8: Generate report
    console.print("[bold blue]Generating report...[/]")
    report_content = generate_report(G, analysis, health, fitness, cluster_info)
    report_path = out_path / "NEURON_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content)

    # Phase 9: Export
    console.print("[bold blue]Exporting...[/]")
    export_formats = formats or {"json", "html"}
    from .export import export_all
    paths = export_all(G, out_path, health.to_dict(), cluster_info, export_formats)
    for fmt, path in paths.items():
        console.print(f"  {fmt}: {path}")

    console.print(f"\n[bold green]Done![/] Output: {out_path}")

    return {
        "stats": stats,
        "health": health.to_dict(),
        "analysis": analysis.to_dict(),
        "cluster": {
            "method": cluster_info["method"],
            "count": cluster_info["stats"]["count"],
        },
        "fitness": fitness.to_dict() if fitness else None,
        "output_dir": str(out_path),
    }


@click.group()
@click.version_option(version="0.1.0", prog_name="neuron")
def cli():
    """Neuron — Transform any codebase into a queryable, scored knowledge graph."""
    pass


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("-o", "--output", default=".neuron-out", help="Output directory")
@click.option("--directed/--undirected", default=False, help="Build directed graph")
@click.option("--resolution", default=1.0, type=float, help="Clustering resolution")
@click.option("--fitness", default=None, type=click.Path(), help="Fitness rules YAML")
@click.option("--format", "formats", multiple=True, help="Export formats (json,html,svg,graphml,obsidian,cypher)")
@click.option("--prune-external/--keep-external", default=False, help="Remove external reference nodes")
def build(path, output, directed, resolution, fitness, formats, prune_external):
    """Build a knowledge graph from a directory."""
    fmt_set = set(formats) if formats else None
    start = time.time()
    result = _run_pipeline(
        path, output, directed, resolution, fitness, fmt_set, prune_external,
    )
    elapsed = time.time() - start
    console.print(f"\nCompleted in {elapsed:.1f}s")

    if "error" not in result:
        _print_summary(result)


@cli.command()
@click.argument("query")
@click.option("--graph", default=".neuron-out/graph.json", help="Path to graph.json")
@click.option("--depth", default=2, type=int, help="Traversal depth")
@click.option("--max-tokens", default=4000, type=int, help="Token budget")
def query(query, graph, depth, max_tokens):
    """Query the knowledge graph."""
    from .serve import query_graph
    from networkx.readwrite import json_graph

    G = json_graph.node_link_graph(json.loads(Path(graph).read_text()))
    result = query_graph(G, query, depth, max_tokens)

    if not result["nodes"]:
        console.print(f"[yellow]No results for '{query}'[/]")
        return

    table = Table(title=f"Results for '{query}'")
    table.add_column("Node", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("File", style="dim")
    table.add_column("Degree", justify="right")

    for node in result["nodes"]:
        table.add_row(
            node["label"], node.get("kind", ""), node.get("file", ""),
            str(node.get("degree", 0)),
        )

    console.print(table)
    console.print(f"\n{len(result['edges'])} edges, ~{result['token_estimate']} tokens")


@cli.command()
@click.argument("old_path", type=click.Path(exists=True))
@click.argument("new_path", type=click.Path(exists=True))
def diff(old_path, new_path):
    """Compare two graph snapshots."""
    from .diff import diff_from_files

    result = diff_from_files(old_path, new_path)

    console.print(Panel(result.summary(), title="Graph Diff", border_style="blue"))

    if result.node_changes:
        table = Table(title="Node Changes")
        table.add_column("Change", style="bold")
        table.add_column("Node")
        table.add_column("Kind")

        for c in result.node_changes[:20]:
            style = {"added": "green", "removed": "red", "modified": "yellow"}.get(c.change, "")
            table.add_row(c.change, c.label, c.kind, style=style)

        console.print(table)

    console.print(f"\nDrift score: {result.drift_score:.2%}")


@cli.command()
@click.option("--graph", default=".neuron-out/graph.json", help="Path to graph.json")
def health(graph):
    """Show health scores for the codebase."""
    from .health import compute_health
    from networkx.readwrite import json_graph

    G = json_graph.node_link_graph(json.loads(Path(graph).read_text()))
    report = compute_health(G)

    grade_colors = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}
    color = grade_colors.get(report.grade, "white")
    console.print(Panel(
        f"[bold {color}]{report.grade}[/] ({report.overall_score:.0%})",
        title="Codebase Health",
        border_style=color,
    ))

    if report.modules:
        table = Table(title="Module Health")
        table.add_column("Module")
        table.add_column("Grade", justify="center")
        table.add_column("Coupling", justify="right")
        table.add_column("Cohesion", justify="right")
        table.add_column("Complexity", justify="right")
        table.add_column("Score", justify="right")

        for m in report.modules:
            mc = grade_colors.get(m.grade, "white")
            table.add_row(
                m.module, f"[{mc}]{m.grade}[/]",
                f"{m.coupling_score:.2f}", f"{m.cohesion_score:.2f}",
                f"{m.complexity_score:.2f}", f"{m.overall_score:.2f}",
            )

        console.print(table)

    if report.recommendations:
        console.print("\n[bold]Recommendations:[/]")
        for rec in report.recommendations:
            console.print(f"  - {rec}")


@cli.command()
@click.option("--graph", default=".neuron-out/graph.json", help="Path to graph.json")
@click.option("--rules", default="neuron-fitness.yaml", help="Fitness rules YAML")
def fitness(graph, rules):
    """Check architecture fitness rules."""
    from .fitness import evaluate, generate_default_rules, load_rules
    from networkx.readwrite import json_graph

    rules_path = Path(rules)
    if not rules_path.is_file():
        console.print(f"[yellow]No rules file found at {rules}[/]")
        console.print("Generate one with: neuron fitness-init")
        return

    G = json_graph.node_link_graph(json.loads(Path(graph).read_text()))
    rule_list = load_rules(rules_path)
    report = evaluate(G, rule_list)

    status = "[green]PASS[/]" if report.is_healthy else "[red]FAIL[/]"
    console.print(f"Fitness: {status} ({report.passed}/{report.rules_checked} rules passed)")

    if report.violations:
        table = Table(title="Violations")
        table.add_column("Severity")
        table.add_column("Rule")
        table.add_column("Message")

        for v in report.violations:
            sev_style = {"error": "red", "warning": "yellow", "info": "blue"}.get(v.severity, "")
            table.add_row(f"[{sev_style}]{v.severity}[/]", v.rule, v.message)

        console.print(table)


@cli.command(name="fitness-init")
@click.option("-o", "--output", default="neuron-fitness.yaml", help="Output path")
def fitness_init(output):
    """Generate a default fitness rules template."""
    from .fitness import generate_default_rules

    content = generate_default_rules()
    Path(output).write_text(content)
    console.print(f"[green]Created {output}[/]")


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("-o", "--output", default=".neuron-out", help="Output directory")
def watch(path, output):
    """Watch for file changes and auto-rebuild."""
    from .watch import watch as do_watch

    def on_change(changed: list[str]):
        console.print(f"[blue]Rebuilding...[/]")
        _run_pipeline(path, output)

    do_watch(path, on_change)


@cli.command()
@click.argument("graph_path", default=".neuron-out/graph.json", type=click.Path(exists=True))
def serve(graph_path):
    """Start the MCP server for graph queries."""
    from .serve import run_mcp_server
    run_mcp_server(graph_path)


@cli.command()
@click.argument("graph_path", default=".neuron-out/graph.json", type=click.Path(exists=True))
def explore(graph_path):
    """Interactive terminal graph explorer."""
    from .tui import explore as do_explore
    do_explore(graph_path)


def _print_summary(result: dict):
    """Print a summary panel after build."""
    stats = result.get("stats", {})
    health = result.get("health", {})
    analysis = result.get("analysis", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")

    table.add_row("Nodes", str(stats.get("nodes", 0)))
    table.add_row("Edges", str(stats.get("edges", 0)))
    table.add_row("Communities", str(result.get("cluster", {}).get("count", 0)))
    table.add_row("Health", f"{health.get('grade', '?')} ({health.get('overall_score', 0):.0%})")
    table.add_row("God Nodes", str(len(analysis.get("god_nodes", []))))
    table.add_row("Bridge Nodes", str(len(analysis.get("bridge_nodes", []))))

    console.print(Panel(table, title="[bold]Neuron Summary[/]", border_style="green"))


if __name__ == "__main__":
    cli()

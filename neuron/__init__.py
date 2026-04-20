"""Neuron — transform any codebase into a queryable, scored knowledge graph."""

__version__ = "0.1.0"


def __getattr__(name: str):
    """Lazy imports for heavy modules."""
    _imports = {
        "detect": "neuron.detect",
        "extract": "neuron.extract",
        "build": "neuron.build",
        "cluster": "neuron.cluster",
        "analyze": "neuron.analyze",
        "health": "neuron.health",
        "fitness": "neuron.fitness",
        "diff": "neuron.diff",
        "report": "neuron.report",
        "export": "neuron.export",
        "serve": "neuron.serve",
        "cache": "neuron.cache",
        "watch": "neuron.watch",
    }
    if name in _imports:
        import importlib

        return importlib.import_module(_imports[name])
    raise AttributeError(f"module 'neuron' has no attribute {name!r}")

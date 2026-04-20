"""Multi-layer extraction: AST (tree-sitter) + dependency manifests + semantic."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .detect import DetectedFile, FileKind


class Confidence(str, Enum):
    EXTRACTED = "extracted"   # Deterministic from source (AST, manifest)
    INFERRED = "inferred"     # LLM/heuristic derived, with score
    AMBIGUOUS = "ambiguous"   # Flagged for human review


@dataclass
class Entity:
    """A named entity extracted from source."""
    name: str
    kind: str  # function, class, method, interface, module, package, variable, type
    file: str
    line: int | None = None
    end_line: int | None = None
    docstring: str | None = None
    signature: str | None = None
    decorators: list[str] = field(default_factory=list)
    visibility: str = "public"  # public, private, protected
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    """A relationship between two entities."""
    source: str
    target: str
    kind: str  # imports, calls, contains, inherits, implements, depends_on, uses, similar_to
    confidence: Confidence = Confidence.EXTRACTED
    score: float = 1.0
    file: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of extracting from a single file."""
    file: str
    file_hash: str
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    language: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "file_hash": self.file_hash,
            "language": self.language,
            "entities": [
                {
                    "name": e.name,
                    "kind": e.kind,
                    "file": e.file,
                    "line": e.line,
                    "end_line": e.end_line,
                    "docstring": e.docstring,
                    "signature": e.signature,
                    "decorators": e.decorators,
                    "visibility": e.visibility,
                    "metadata": e.metadata,
                }
                for e in self.entities
            ],
            "relations": [
                {
                    "source": r.source,
                    "target": r.target,
                    "kind": r.kind,
                    "confidence": r.confidence.value,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in self.relations
            ],
            "errors": self.errors,
        }


# ── Tree-sitter language loading ──────────────────────────────────────

_TS_LANGUAGE_MAP: dict[str, str] = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "java": "tree_sitter_java",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
    "ruby": "tree_sitter_ruby",
    "c_sharp": "tree_sitter_c_sharp",
}

_loaded_languages: dict[str, Any] = {}
_loaded_parsers: dict[str, Any] = {}


def _get_parser(language: str):
    """Get or create a tree-sitter parser for the given language."""
    if language in _loaded_parsers:
        return _loaded_parsers[language], _loaded_languages[language]

    module_name = _TS_LANGUAGE_MAP.get(language)
    if not module_name:
        return None, None

    try:
        import importlib
        import tree_sitter as ts

        mod = importlib.import_module(module_name)

        # tree-sitter >= 0.23 uses language() function
        if language == "typescript":
            lang_obj = ts.Language(mod.language_typescript())
        else:
            lang_obj = ts.Language(mod.language())

        parser = ts.Parser(lang_obj)
        _loaded_languages[language] = lang_obj
        _loaded_parsers[language] = parser
        return parser, lang_obj
    except Exception:
        return None, None


def _file_hash(path: Path) -> str:
    """SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ── Python extraction ─────────────────────────────────────────────────

def _extract_python(source: bytes, filepath: str, tree) -> ExtractionResult:
    """Extract entities and relations from Python using tree-sitter AST."""
    result = ExtractionResult(file=filepath, file_hash="", language="python")
    root = tree.root_node

    module_name = Path(filepath).stem

    def _get_text(node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _get_docstring(body_node) -> str | None:
        if body_node and body_node.type == "block" and body_node.child_count > 0:
            first = body_node.children[0]
            if first.type == "expression_statement" and first.child_count > 0:
                expr = first.children[0]
                if expr.type == "string":
                    text = _get_text(expr).strip("\"'")
                    return text[:500]
        return None

    def _get_decorators(node) -> list[str]:
        decorators = []
        if node.prev_named_sibling and node.prev_named_sibling.type == "decorator":
            decorators.append(_get_text(node.prev_named_sibling))
        # Also check parent for decorated_definition
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    decorators.append(_get_text(child).lstrip("@"))
        return decorators

    def _visit_class(node, prefix: str = ""):
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = _get_text(name_node)
        full_name = f"{prefix}{name}" if prefix else name

        body = node.child_by_field_name("body")

        # Superclasses
        superclasses = []
        arg_list = node.child_by_field_name("superclasses")
        if arg_list:
            for arg in arg_list.named_children:
                superclasses.append(_get_text(arg))

        entity = Entity(
            name=full_name,
            kind="class",
            file=filepath,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            docstring=_get_docstring(body),
            decorators=_get_decorators(node),
            metadata={"superclasses": superclasses} if superclasses else {},
        )
        result.entities.append(entity)

        # Inheritance relations
        for sc in superclasses:
            result.relations.append(Relation(
                source=full_name, target=sc, kind="inherits",
                file=filepath,
            ))

        # Contains relation
        result.relations.append(Relation(
            source=module_name, target=full_name, kind="contains",
            file=filepath,
        ))

        # Visit methods inside class
        if body:
            for child in body.named_children:
                if child.type == "function_definition":
                    _visit_function(child, prefix=f"{full_name}.")
                elif child.type == "decorated_definition":
                    for sub in child.named_children:
                        if sub.type == "function_definition":
                            _visit_function(sub, prefix=f"{full_name}.")

    def _visit_function(node, prefix: str = ""):
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = _get_text(name_node)
        full_name = f"{prefix}{name}" if prefix else name

        params = node.child_by_field_name("parameters")
        sig = _get_text(params) if params else "()"
        body = node.child_by_field_name("body")

        visibility = "private" if name.startswith("_") else "public"
        kind = "method" if prefix else "function"

        entity = Entity(
            name=full_name,
            kind=kind,
            file=filepath,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            docstring=_get_docstring(body),
            signature=f"{name}{sig}",
            decorators=_get_decorators(node),
            visibility=visibility,
        )
        result.entities.append(entity)

        if not prefix:
            result.relations.append(Relation(
                source=module_name, target=full_name, kind="contains",
                file=filepath,
            ))

        # Extract function calls within body
        if body:
            _extract_calls(body, full_name, source, filepath, result)

    def _extract_calls(node, caller: str, src: bytes, fpath: str, res: ExtractionResult):
        """Recursively find call expressions."""
        for child in node.children:
            if child.type == "call":
                func_node = child.child_by_field_name("function")
                if func_node:
                    callee = _get_text(func_node)
                    # Skip built-ins and very common calls
                    if callee not in {"print", "len", "range", "str", "int", "float", "list", "dict", "set", "tuple", "type", "isinstance", "hasattr", "getattr", "super"}:
                        res.relations.append(Relation(
                            source=caller, target=callee, kind="calls",
                            confidence=Confidence.EXTRACTED,
                            file=fpath,
                        ))
            _extract_calls(child, caller, src, fpath, res)

    # Extract imports
    for child in root.children:
        if child.type == "import_statement":
            for name_child in child.named_children:
                mod = _get_text(name_child)
                result.relations.append(Relation(
                    source=module_name, target=mod, kind="imports",
                    file=filepath,
                ))
        elif child.type == "import_from_statement":
            mod_node = child.child_by_field_name("module_name")
            if mod_node:
                mod = _get_text(mod_node)
                result.relations.append(Relation(
                    source=module_name, target=mod, kind="imports",
                    file=filepath,
                ))

    # Module-level entity
    result.entities.append(Entity(
        name=module_name,
        kind="module",
        file=filepath,
        line=1,
    ))

    # Visit top-level definitions
    for child in root.children:
        if child.type == "class_definition":
            _visit_class(child)
        elif child.type == "function_definition":
            _visit_function(child)
        elif child.type == "decorated_definition":
            for sub in child.named_children:
                if sub.type == "class_definition":
                    _visit_class(sub)
                elif sub.type == "function_definition":
                    _visit_function(sub)

    return result


# ── Generic extraction (JS/TS/Go/Rust/Java/etc.) ────────────────────

def _extract_generic(source: bytes, filepath: str, tree, language: str) -> ExtractionResult:
    """Generic entity extraction using tree-sitter node types."""
    result = ExtractionResult(file=filepath, file_hash="", language=language)
    root = tree.root_node
    module_name = Path(filepath).stem

    def _get_text(node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    result.entities.append(Entity(name=module_name, kind="module", file=filepath, line=1))

    # Function/method definition node types per language
    func_types = {
        "javascript": {"function_declaration", "method_definition", "arrow_function"},
        "typescript": {"function_declaration", "method_definition", "arrow_function"},
        "go": {"function_declaration", "method_declaration"},
        "rust": {"function_item", "impl_item"},
        "java": {"method_declaration", "constructor_declaration"},
        "c": {"function_definition"},
        "cpp": {"function_definition"},
        "ruby": {"method", "singleton_method"},
        "c_sharp": {"method_declaration", "constructor_declaration"},
    }
    class_types = {
        "javascript": {"class_declaration"},
        "typescript": {"class_declaration", "interface_declaration", "type_alias_declaration"},
        "go": {"type_declaration"},
        "rust": {"struct_item", "enum_item", "trait_item"},
        "java": {"class_declaration", "interface_declaration", "enum_declaration"},
        "c": {"struct_specifier"},
        "cpp": {"class_specifier", "struct_specifier"},
        "ruby": {"class", "module"},
        "c_sharp": {"class_declaration", "interface_declaration", "struct_declaration"},
    }
    import_types = {
        "javascript": {"import_statement"},
        "typescript": {"import_statement"},
        "go": {"import_declaration"},
        "rust": {"use_declaration"},
        "java": {"import_declaration"},
        "c": {"preproc_include"},
        "cpp": {"preproc_include"},
        "ruby": {"call"},  # require/require_relative
        "c_sharp": {"using_directive"},
    }

    ft = func_types.get(language, set())
    ct = class_types.get(language, set())
    it = import_types.get(language, set())

    def _walk(node, depth: int = 0):
        if depth > 50:
            return

        if node.type in ct:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _get_text(name_node)
                result.entities.append(Entity(
                    name=name,
                    kind="class" if "class" in node.type or "struct" in node.type else "interface",
                    file=filepath,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))
                result.relations.append(Relation(
                    source=module_name, target=name, kind="contains",
                    file=filepath,
                ))

        if node.type in ft:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _get_text(name_node)
                result.entities.append(Entity(
                    name=name,
                    kind="function",
                    file=filepath,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))
                result.relations.append(Relation(
                    source=module_name, target=name, kind="contains",
                    file=filepath,
                ))

        if node.type in it:
            text = _get_text(node)
            # Try to extract the module name from the import
            # Handle common patterns
            parts = re.findall(r'["\']([^"\']+)["\']', text)
            if parts:
                for p in parts:
                    result.relations.append(Relation(
                        source=module_name, target=p, kind="imports",
                        file=filepath,
                    ))
            else:
                # For Go/Rust/Java style imports
                for child in node.named_children:
                    mod = _get_text(child).strip('"').strip("'")
                    if mod:
                        result.relations.append(Relation(
                            source=module_name, target=mod, kind="imports",
                            file=filepath,
                        ))

        for child in node.children:
            _walk(child, depth + 1)

    _walk(root)
    return result


# ── Manifest (dependency) extraction ─────────────────────────────────

def extract_manifest(detected: DetectedFile) -> ExtractionResult:
    """Extract dependencies from package manifests."""
    result = ExtractionResult(
        file=detected.relative,
        file_hash=_file_hash(detected.path),
        language="manifest",
    )

    try:
        content = detected.path.read_text(errors="replace")
    except OSError as e:
        result.errors.append(str(e))
        return result

    project_name = detected.path.parent.name
    result.entities.append(Entity(
        name=project_name, kind="project", file=detected.relative, line=1,
    ))

    mtype = detected.manifest_type

    if mtype == "npm" and detected.path.name == "package.json":
        _extract_npm_deps(content, project_name, detected.relative, result)
    elif mtype == "python" and detected.path.name == "pyproject.toml":
        _extract_pyproject_deps(content, project_name, detected.relative, result)
    elif mtype == "cargo" and detected.path.name == "Cargo.toml":
        _extract_cargo_deps(content, project_name, detected.relative, result)
    elif mtype == "go" and detected.path.name == "go.mod":
        _extract_go_deps(content, project_name, detected.relative, result)
    elif mtype == "pip" and detected.path.name == "requirements.txt":
        _extract_requirements_deps(content, project_name, detected.relative, result)

    return result


def _extract_npm_deps(content: str, project: str, filepath: str, result: ExtractionResult):
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return

    for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(dep_key, {})
        for pkg, version in deps.items():
            result.entities.append(Entity(
                name=pkg, kind="package", file=filepath,
                metadata={"version": version, "dep_type": dep_key},
            ))
            result.relations.append(Relation(
                source=project, target=pkg, kind="depends_on",
                file=filepath,
                metadata={"version": version, "dep_type": dep_key},
            ))


def _extract_pyproject_deps(content: str, project: str, filepath: str, result: ExtractionResult):
    # Simple TOML-like parsing for dependencies
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            continue
        if "dependencies" in stripped and "=" in stripped:
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                in_deps = False
                continue
            if stripped.startswith("[") and not stripped.startswith('["'):
                in_deps = False
                continue
            # Extract package name from dependency string
            dep = stripped.strip('", ')
            if dep:
                pkg = re.split(r"[>=<!\[\];]", dep)[0].strip()
                if pkg:
                    result.entities.append(Entity(
                        name=pkg, kind="package", file=filepath,
                    ))
                    result.relations.append(Relation(
                        source=project, target=pkg, kind="depends_on",
                        file=filepath,
                    ))


def _extract_cargo_deps(content: str, project: str, filepath: str, result: ExtractionResult):
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]" or stripped.startswith("[dependencies.") or stripped == "[dev-dependencies]":
            in_deps = True
            continue
        if stripped.startswith("[") and "dependencies" not in stripped:
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            pkg = stripped.split("=")[0].strip()
            if pkg:
                result.entities.append(Entity(
                    name=pkg, kind="package", file=filepath,
                ))
                result.relations.append(Relation(
                    source=project, target=pkg, kind="depends_on",
                    file=filepath,
                ))


def _extract_go_deps(content: str, project: str, filepath: str, result: ExtractionResult):
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require") or stripped.startswith("//") or stripped in ("(", ")"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and "/" in parts[0]:
            pkg = parts[0]
            result.entities.append(Entity(
                name=pkg, kind="package", file=filepath,
            ))
            result.relations.append(Relation(
                source=project, target=pkg, kind="depends_on",
                file=filepath,
            ))


def _extract_requirements_deps(content: str, project: str, filepath: str, result: ExtractionResult):
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        pkg = re.split(r"[>=<!\[\];~]", stripped)[0].strip()
        if pkg:
            result.entities.append(Entity(
                name=pkg, kind="package", file=filepath,
            ))
            result.relations.append(Relation(
                source=project, target=pkg, kind="depends_on",
                file=filepath,
            ))


# ── Main extraction entry points ─────────────────────────────────────

_LANG_EXTRACTORS = {
    "python": _extract_python,
}


def extract_file(detected: DetectedFile) -> ExtractionResult:
    """Extract entities and relations from a single source file.

    Uses tree-sitter AST for deterministic, zero-cost code extraction.
    """
    if detected.kind == FileKind.MANIFEST:
        return extract_manifest(detected)

    if detected.kind != FileKind.CODE:
        # Return minimal result for non-code files
        return ExtractionResult(
            file=detected.relative,
            file_hash=_file_hash(detected.path),
            language=detected.language,
            entities=[Entity(
                name=Path(detected.relative).stem,
                kind="document",
                file=detected.relative,
                line=1,
            )],
        )

    try:
        source = detected.path.read_bytes()
    except OSError as e:
        return ExtractionResult(
            file=detected.relative,
            file_hash="",
            language=detected.language,
            errors=[str(e)],
        )

    fhash = _file_hash(detected.path)
    parser, lang = _get_parser(detected.language)

    if parser is None:
        # No tree-sitter parser available — return basic module entity
        return ExtractionResult(
            file=detected.relative,
            file_hash=fhash,
            language=detected.language,
            entities=[Entity(
                name=Path(detected.relative).stem,
                kind="module",
                file=detected.relative,
                line=1,
            )],
        )

    tree = parser.parse(source)

    # Use language-specific extractor if available, else generic
    extractor = _LANG_EXTRACTORS.get(detected.language, _extract_generic)

    if extractor == _extract_generic:
        result = extractor(source, detected.relative, tree, detected.language)
    else:
        result = extractor(source, detected.relative, tree)

    result.file_hash = fhash
    return result


def extract_all(files: list[DetectedFile]) -> list[ExtractionResult]:
    """Extract from all detected files."""
    results = []
    for f in files:
        results.append(extract_file(f))
    return results

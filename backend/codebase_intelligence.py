"""
Ombra Codebase Intelligence
============================
AST parsing, file dependency graph, semantic code search,
and symbol indexing for deep codebase understanding.
"""

import os
import ast
import json
import re
import hashlib
import time
from pathlib import Path
from typing import Optional
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".css": "css",
    ".html": "html",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sql": "sql",
}

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".cache",
    ".tox", ".mypy_cache", ".pytest_cache", "coverage",
    ".idea", ".vscode", "vendor", "target",
}

MAX_FILE_SIZE = 512 * 1024  # 512 KB


# ── AST Analysis (Python) ────────────────────────────────────────────────────

class PythonAnalyzer:
    """Extract structure from Python files using the ast module."""

    @staticmethod
    def analyze(source: str, filepath: str = "") -> dict:
        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            return {"error": f"SyntaxError: {e}", "filepath": filepath}

        result = {
            "filepath": filepath,
            "language": "python",
            "imports": [],
            "classes": [],
            "functions": [],
            "global_vars": [],
            "decorators": [],
            "docstring": ast.get_docstring(tree),
            "line_count": len(source.splitlines()),
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append({
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    result["imports"].append({
                        "module": f"{module}.{alias.name}",
                        "from": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })

            elif isinstance(node, ast.ClassDef):
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.dump(base))
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "args": [a.arg for a in item.args.args if a.arg != "self"],
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "line": item.lineno,
                            "docstring": ast.get_docstring(item),
                            "decorators": [_decorator_name(d) for d in item.decorator_list],
                        })
                result["classes"].append({
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "decorators": [_decorator_name(d) for d in node.decorator_list],
                })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only top-level functions (not methods)
                if not any(isinstance(p, ast.ClassDef) for p in ast.walk(tree)
                           if hasattr(p, 'body') and node in getattr(p, 'body', [])):
                    result["functions"].append({
                        "name": node.name,
                        "args": [a.arg for a in node.args.args],
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "line": node.lineno,
                        "end_line": node.end_lineno,
                        "docstring": ast.get_docstring(node),
                        "decorators": [_decorator_name(d) for d in node.decorator_list],
                        "returns": _annotation_str(node.returns) if node.returns else None,
                    })

            elif isinstance(node, ast.Assign) and hasattr(node, 'lineno'):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        result["global_vars"].append({
                            "name": target.id,
                            "line": node.lineno,
                        })

        return result


def _decorator_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_decorator_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _annotation_str(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Attribute):
        return f"{_annotation_str(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        return f"{_annotation_str(node.value)}[{_annotation_str(node.slice)}]"
    return ast.dump(node)


# ── JavaScript/TypeScript Regex Analyzer ──────────────────────────────────────

class JSAnalyzer:
    """Regex-based structure extraction for JS/TS files."""

    _IMPORT_RE = re.compile(
        r'''(?:import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)?\s*(?:,\s*{[^}]+})?\s*from\s+['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\))''',
        re.MULTILINE,
    )
    _FUNC_RE = re.compile(
        r'''(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)''',
        re.MULTILINE,
    )
    _ARROW_RE = re.compile(
        r'''(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>''',
        re.MULTILINE,
    )
    _CLASS_RE = re.compile(
        r'''(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?''',
        re.MULTILINE,
    )
    _EXPORT_RE = re.compile(
        r'''export\s+(?:default\s+)?(?:const|let|var|function|class|async)\s+(\w+)''',
        re.MULTILINE,
    )

    @staticmethod
    def analyze(source: str, filepath: str = "") -> dict:
        result = {
            "filepath": filepath,
            "language": "javascript",
            "imports": [],
            "functions": [],
            "classes": [],
            "exports": [],
            "line_count": len(source.splitlines()),
        }

        for m in JSAnalyzer._IMPORT_RE.finditer(source):
            module = m.group(1) or m.group(2)
            result["imports"].append({"module": module, "line": source[:m.start()].count("\n") + 1})

        for m in JSAnalyzer._FUNC_RE.finditer(source):
            result["functions"].append({
                "name": m.group(1),
                "args": [a.strip() for a in m.group(2).split(",") if a.strip()],
                "line": source[:m.start()].count("\n") + 1,
            })

        for m in JSAnalyzer._ARROW_RE.finditer(source):
            result["functions"].append({
                "name": m.group(1),
                "args": [a.strip() for a in m.group(2).split(",") if a.strip()],
                "line": source[:m.start()].count("\n") + 1,
                "arrow": True,
            })

        for m in JSAnalyzer._CLASS_RE.finditer(source):
            result["classes"].append({
                "name": m.group(1),
                "extends": m.group(2),
                "line": source[:m.start()].count("\n") + 1,
            })

        for m in JSAnalyzer._EXPORT_RE.finditer(source):
            result["exports"].append({"name": m.group(1), "line": source[:m.start()].count("\n") + 1})

        return result


# ── File Dependency Graph ─────────────────────────────────────────────────────

class FileGraph:
    """
    Build and query an import/dependency graph across the codebase.
    Nodes = files, Edges = import relationships.
    """

    def __init__(self):
        self.nodes: dict[str, dict] = {}     # filepath -> file metadata
        self.edges: list[dict] = []          # {from, to, type}
        self.reverse_edges: dict[str, list[str]] = defaultdict(list)  # file -> importers
        self._symbol_index: dict[str, list[dict]] = defaultdict(list)  # symbol -> [locations]
        self._last_build: float = 0

    def build(self, root_dir: str, force: bool = False) -> dict:
        """Scan a directory and build the full file graph."""
        start = time.time()
        file_count = 0
        error_count = 0

        self.nodes.clear()
        self.edges.clear()
        self.reverse_edges.clear()
        self._symbol_index.clear()

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Skip ignored directories
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                fpath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(fpath, root_dir)

                if os.path.getsize(fpath) > MAX_FILE_SIZE:
                    continue

                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        source = f.read()
                except (IOError, OSError):
                    error_count += 1
                    continue

                lang = SUPPORTED_EXTENSIONS[ext]
                analysis = self._analyze_file(source, rel_path, lang)

                # Content hash for change detection
                content_hash = hashlib.md5(source.encode()).hexdigest()

                self.nodes[rel_path] = {
                    "path": rel_path,
                    "language": lang,
                    "size": len(source),
                    "lines": analysis.get("line_count", 0),
                    "hash": content_hash,
                    "analysis": analysis,
                }

                # Index symbols
                for func in analysis.get("functions", []):
                    self._symbol_index[func["name"]].append({
                        "file": rel_path, "type": "function", "line": func.get("line"),
                    })
                for cls in analysis.get("classes", []):
                    self._symbol_index[cls["name"]].append({
                        "file": rel_path, "type": "class", "line": cls.get("line"),
                    })
                for var in analysis.get("global_vars", []):
                    self._symbol_index[var["name"]].append({
                        "file": rel_path, "type": "variable", "line": var.get("line"),
                    })

                # Build edges from imports
                for imp in analysis.get("imports", []):
                    module = imp.get("module", "")
                    resolved = self._resolve_import(module, rel_path, root_dir, lang)
                    if resolved:
                        self.edges.append({
                            "from": rel_path,
                            "to": resolved,
                            "import": module,
                        })
                        self.reverse_edges[resolved].append(rel_path)

                file_count += 1

        self._last_build = time.time()
        return {
            "files_indexed": file_count,
            "edges": len(self.edges),
            "symbols": sum(len(v) for v in self._symbol_index.values()),
            "errors": error_count,
            "duration_ms": int((time.time() - start) * 1000),
        }

    def _analyze_file(self, source: str, filepath: str, lang: str) -> dict:
        if lang == "python":
            return PythonAnalyzer.analyze(source, filepath)
        elif lang in ("javascript", "typescript"):
            return JSAnalyzer.analyze(source, filepath)
        else:
            # Basic line-count only for unsupported languages
            return {"filepath": filepath, "language": lang, "line_count": len(source.splitlines())}

    def _resolve_import(self, module: str, from_file: str, root_dir: str, lang: str) -> str | None:
        """Try to resolve an import string to a file in the graph."""
        if lang == "python":
            # Convert module.path to file path
            parts = module.split(".")
            candidates = [
                os.path.join(*parts) + ".py",
                os.path.join(*parts, "__init__.py"),
            ]
        elif lang in ("javascript", "typescript"):
            if not module.startswith("."):
                return None  # External package
            from_dir = os.path.dirname(from_file)
            base = os.path.normpath(os.path.join(from_dir, module))
            candidates = [
                base + ".js", base + ".ts", base + ".jsx", base + ".tsx",
                base + "/index.js", base + "/index.ts",
            ]
        else:
            return None

        for candidate in candidates:
            normalized = candidate.replace("\\", "/")
            if normalized in self.nodes:
                return normalized
        return None

    def search_symbol(self, query: str, limit: int = 20) -> list[dict]:
        """Search for symbols (functions, classes, variables) by name pattern."""
        results = []
        query_lower = query.lower()
        for symbol, locations in self._symbol_index.items():
            if query_lower in symbol.lower():
                for loc in locations:
                    results.append({"symbol": symbol, **loc})
                    if len(results) >= limit:
                        return results
        return results

    def get_dependents(self, filepath: str) -> list[str]:
        """Get all files that import this file."""
        return self.reverse_edges.get(filepath, [])

    def get_dependencies(self, filepath: str) -> list[str]:
        """Get all files this file imports."""
        return [e["to"] for e in self.edges if e["from"] == filepath]

    def get_file_info(self, filepath: str) -> dict | None:
        """Get full analysis for a file."""
        return self.nodes.get(filepath)

    def get_related_files(self, filepath: str, depth: int = 2) -> list[str]:
        """Get files related to a given file within N hops."""
        visited = set()
        queue = [(filepath, 0)]
        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            for dep in self.get_dependencies(current) + self.get_dependents(current):
                if dep not in visited:
                    queue.append((dep, d + 1))
        visited.discard(filepath)
        return list(visited)

    def get_stats(self) -> dict:
        """Summary stats for the indexed codebase."""
        langs = defaultdict(int)
        total_lines = 0
        for node in self.nodes.values():
            langs[node["language"]] += 1
            total_lines += node.get("lines", 0)
        return {
            "total_files": len(self.nodes),
            "total_lines": total_lines,
            "total_symbols": sum(len(v) for v in self._symbol_index.values()),
            "total_edges": len(self.edges),
            "languages": dict(langs),
            "last_build": self._last_build,
        }

    def search_code(self, query: str, root_dir: str, max_results: int = 20) -> list[dict]:
        """
        Search for code matching a text pattern across all indexed files.
        Returns matching lines with context.
        """
        results = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for rel_path, node in self.nodes.items():
            fpath = os.path.join(root_dir, rel_path)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except (IOError, OSError):
                continue

            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    ctx_start = max(0, i - 3)
                    ctx_end = min(len(lines), i + 2)
                    results.append({
                        "file": rel_path,
                        "line": i,
                        "match": line.rstrip(),
                        "context": "".join(lines[ctx_start:ctx_end]),
                        "language": node["language"],
                    })
                    if len(results) >= max_results:
                        return results
        return results


# ── Global instance ───────────────────────────────────────────────────────────
file_graph = FileGraph()

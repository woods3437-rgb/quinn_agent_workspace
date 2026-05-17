from __future__ import annotations

import ast
import re
from pathlib import Path

from .models import CodeDependency, CodeSymbol, RepoFile


IMPORT_RE = re.compile(
    r"^\s*import\s+(?:type\s+)?(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
REQUIRE_RE = re.compile(r"require\(['\"]([^'\"]+)['\"]\)")
EXPORT_FUNC_RE = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)"
)
EXPORT_CONST_RE = re.compile(
    r"export\s+(?:default\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)"
)
CONST_FUNC_RE = re.compile(
    r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*(?::\s*[A-Za-z0-9_<>\[\],\s|]+)?\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
)
CLASS_RE = re.compile(r"(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_]+)")
HTTP_VERB_RE = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)"
)

PY_ROUTE_DECORATORS = {
    "app.get",
    "app.post",
    "app.put",
    "app.patch",
    "app.delete",
    "app.options",
    "app.head",
    "router.get",
    "router.post",
    "router.put",
    "router.patch",
    "router.delete",
    "router.options",
    "router.head",
}
PY_FRAMEWORK_DECORATORS = {"route", "get", "post", "put", "patch", "delete"}


class CodeIntelligence:
    """AST-aware code intelligence for Python and TS/JS/TSX.

    Phase 6 — internal use only. Strictly read-only; never executes user code.
    """

    def analyze(
        self, root: Path, repo_file: RepoFile
    ) -> tuple[list[CodeSymbol], list[CodeDependency]]:
        path = root / repo_file.path
        try:
            if repo_file.language == "python":
                return self._python(path, repo_file)
            if repo_file.language in {
                "typescript",
                "typescript-react",
                "javascript",
                "javascript-react",
            }:
                return self._js_like(path, repo_file)
        except OSError:
            return [], []
        return [], []

    def _python(self, path: Path, repo_file: RepoFile):
        text = self._read(path)
        symbols: list[CodeSymbol] = []
        deps: list[CodeDependency] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return [], []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind, route_path = self._classify_python_function(node)
                signature = self._python_signature(node)
                symbol = self._symbol(
                    repo_file,
                    node.name,
                    kind,
                    signature,
                    node.lineno,
                    getattr(node, "end_lineno", None),
                    metadata={"http_path": route_path} if route_path else {},
                )
                symbols.append(symbol)
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    self._symbol(
                        repo_file,
                        node.name,
                        "class",
                        f"class {node.name}",
                        node.lineno,
                        getattr(node, "end_lineno", None),
                    )
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    deps.append(self._dep(repo_file, alias.name, "import"))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.append(self._dep(repo_file, node.module, "import_from"))
        return symbols, deps

    def _classify_python_function(self, node) -> tuple[str, str]:
        for decorator in getattr(node, "decorator_list", []):
            qualified = self._decorator_qualified(decorator)
            route_path = self._decorator_route_path(decorator)
            if qualified in PY_ROUTE_DECORATORS or qualified.endswith(".route"):
                return "api_endpoint", route_path
            short = qualified.split(".")[-1]
            if short in PY_FRAMEWORK_DECORATORS and route_path:
                return "api_endpoint", route_path
        return "function", ""

    def _decorator_qualified(self, decorator) -> str:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        return ".".join(reversed(parts))

    def _decorator_route_path(self, decorator) -> str:
        if isinstance(decorator, ast.Call) and decorator.args:
            first = decorator.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
        return ""

    def _python_signature(self, node) -> str:
        args = [arg.arg for arg in node.args.args]
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        return f"{prefix}{node.name}({', '.join(args)})"

    def _js_like(self, path: Path, repo_file: RepoFile):
        text = self._read(path)
        symbols: list[CodeSymbol] = []
        deps: list[CodeDependency] = []
        seen: set[tuple[str, str]] = set()

        for match in IMPORT_RE.finditer(text):
            deps.append(self._dep(repo_file, match.group(1), "import"))
        for match in REQUIRE_RE.finditer(text):
            deps.append(self._dep(repo_file, match.group(1), "require"))

        for match in HTTP_VERB_RE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            name = match.group(1)
            symbols.append(
                self._symbol(
                    repo_file,
                    name,
                    "route_handler",
                    f"export function {name}(req)",
                    line,
                    None,
                )
            )
            seen.add((name, "route_handler"))

        for match in EXPORT_FUNC_RE.finditer(text):
            name = match.group(1)
            if (name, "route_handler") in seen:
                continue
            line = text[: match.start()].count("\n") + 1
            kind = "component" if name[:1].isupper() else "function"
            symbols.append(
                self._symbol(
                    repo_file,
                    name,
                    kind,
                    f"{name}({match.group(2)})",
                    line,
                    None,
                )
            )
            seen.add((name, kind))

        for match in EXPORT_CONST_RE.finditer(text):
            name = match.group(1)
            if any((name, kind) in seen for kind in ("component", "function", "export")):
                continue
            line = text[: match.start()].count("\n") + 1
            symbols.append(
                self._symbol(repo_file, name, "export", f"export {name}", line, None)
            )
            seen.add((name, "export"))

        for match in CONST_FUNC_RE.finditer(text):
            name = match.group(1)
            if any((name, kind) in seen for kind in ("component", "function", "route_handler")):
                continue
            line = text[: match.start()].count("\n") + 1
            kind = "component" if name[:1].isupper() else "function"
            symbols.append(
                self._symbol(
                    repo_file,
                    name,
                    kind,
                    match.group(0).split("=")[0].strip(),
                    line,
                    None,
                )
            )
            seen.add((name, kind))

        for match in CLASS_RE.finditer(text):
            name = match.group(1)
            line = text[: match.start()].count("\n") + 1
            symbols.append(
                self._symbol(
                    repo_file, name, "class", f"class {name}", line, None
                )
            )

        if repo_file.path.endswith(("page.tsx", "page.jsx")):
            symbols.append(
                self._symbol(
                    repo_file,
                    repo_file.path,
                    "route",
                    repo_file.path,
                    1,
                    None,
                )
            )
        return symbols, deps

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(errors="ignore")
        except OSError:
            return ""

    def _symbol(
        self,
        repo_file: RepoFile,
        name: str,
        symbol_type: str,
        signature: str,
        line_start: int | None,
        line_end: int | None,
        metadata: dict | None = None,
    ) -> CodeSymbol:
        return CodeSymbol(
            project_id=repo_file.project_id,
            repository_id=repo_file.repository_id,
            file_id=repo_file.id,
            file_path=repo_file.path,
            name=name,
            symbol_type=symbol_type,
            signature=signature,
            line_start=line_start,
            line_end=line_end,
            language=repo_file.language,
            metadata=metadata or {},
        )

    def _dep(
        self, repo_file: RepoFile, dependency: str, dependency_type: str
    ) -> CodeDependency:
        return CodeDependency(
            project_id=repo_file.project_id,
            repository_id=repo_file.repository_id,
            file_id=repo_file.id,
            file_path=repo_file.path,
            dependency=dependency,
            dependency_type=dependency_type,
            source=repo_file.path,
        )

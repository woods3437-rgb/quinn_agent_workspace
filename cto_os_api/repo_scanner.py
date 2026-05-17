from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .file_classifier import FileClassifier
from .models import Repository, RepoFile, RepoFileRole, RepoScan


# Phase 15: extended to cover real-world mobile/web build artifacts that were
# polluting scans (15k files on a dscvr-shaped repo).
IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", "__pycache__", "venv",
    ".venv", "coverage",
    # iOS / Android natives
    "Pods", "DerivedData", ".gradle",
    # Expo / React Native
    ".expo", ".expo-shared", ".metro-cache",
    # JS tooling caches
    ".turbo", ".cache", ".parcel-cache", ".rollup.cache", ".swc",
    # Editor / vendor
    ".idea", "vendor", "target", "out", "tmp",
    # Claude Code worktrees — full copies of the repo
    "worktrees",
}
IGNORE_NAMES = {".env", ".env.local", ".env.production", ".env.development", "secrets.json"}
MAX_FILE_BYTES = 512_000
TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini",
    ".css", ".scss", ".html", ".sql", ".sh", ".Dockerfile", ".dockerignore", ".gitignore",
}
LANGUAGE_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript-react",
    ".js": "javascript",
    ".jsx": "javascript-react",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".css": "css",
    ".html": "html",
    ".sql": "sql",
    ".sh": "shell",
}


class RepoSafetyError(ValueError):
    pass


class RepoScanner:
    def __init__(self, classifier: FileClassifier | None = None) -> None:
        # Phase 16.5: classify every file as we scan; downstream consumers
        # (candidate-files, build packet, review routing) read the result.
        self._classifier = classifier or FileClassifier()

    def resolve_root(self, repository: Repository) -> Path:
        if not repository.local_path:
            raise RepoSafetyError("Repository.local_path is required for local scanning.")
        root = Path(repository.local_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise RepoSafetyError(f"Repository path is not a directory: {root}")
        return root

    def scan(self, project_id: str, repository: Repository) -> tuple[RepoScan, list[RepoFile]]:
        root = self.resolve_root(repository)
        files: list[RepoFile] = []
        package_files: list[str] = []
        routes: list[str] = []
        docs: list[str] = []
        configs: list[str] = []
        tests: list[str] = []
        source_count = 0

        # Phase 15: prefer git's view of the working tree (respects .gitignore
        # and skips ignored files); fall back to a filtered walk.
        extra_ignores = self._parse_gitignore(root)
        candidates = self._enumerate_paths(root)
        for path in candidates:
            if not path.is_file() or self._ignored(path, root, extra_ignores):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > MAX_FILE_BYTES or self._looks_binary(path):
                continue
            relative = path.relative_to(root).as_posix()
            role = self._role(relative)
            language = LANGUAGE_BY_EXT.get(path.suffix, "")
            summary = self._summarize_file(path, relative, role)
            digest = self._hash_file(path)
            classification = self._classifier.classify(relative)
            repo_file = RepoFile(
                project_id=project_id,
                repository_id=repository.id,
                path=relative,
                file_type=path.suffix.lstrip(".") or path.name,
                language=language,
                size_bytes=stat.st_size,
                role=role,
                summary=summary,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                hash=digest,
                semantic_type=classification.semantic_type,
                classification_confidence=classification.confidence,
                classification_rules=list(classification.rules_triggered),
            )
            files.append(repo_file)
            # Phase 16.5: surface the manifest, not the lockfile. Previously
            # ``key_files`` accidentally included package-lock.json / yarn.lock /
            # pnpm-lock.yaml, which then leaked into branch plans + reviews.
            if path.name in {"package.json", "pyproject.toml", "requirements.txt"}:
                package_files.append(relative)
            if role == RepoFileRole.route:
                routes.append(relative)
            if role == RepoFileRole.doc:
                docs.append(relative)
            if role == RepoFileRole.config:
                configs.append(relative)
            if role == RepoFileRole.test:
                tests.append(relative)
            if role in {RepoFileRole.component, RepoFileRole.service, RepoFileRole.model, RepoFileRole.entrypoint, RepoFileRole.route}:
                source_count += 1

        tech_stack, package_managers, frameworks, test_commands, build_commands, lint_commands = self._detect_stack(root)
        risks = []
        if not tests:
            risks.append("No test files detected by scanner.")
        if not docs:
            risks.append("No README/docs files detected.")
        if not package_files:
            risks.append("No package/dependency manifest detected.")

        scan = RepoScan(
            project_id=project_id,
            repository_id=repository.id,
            summary=f"Scanned {len(files)} files. Detected {source_count} source/route/component files, {len(tests)} tests, {len(configs)} configs, and {len(docs)} docs.",
            tech_stack=tech_stack,
            package_managers=package_managers,
            frameworks=frameworks,
            routes=routes[:100],
            key_files=(package_files + docs + configs)[:100],
            test_commands=test_commands,
            build_commands=build_commands,
            lint_commands=lint_commands,
            risks=risks,
        )
        return scan, files

    def _ignored(
        self,
        path: Path,
        root: Path,
        extra_patterns: list[str] | None = None,
    ) -> bool:
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in relative_parts):
            return True
        if path.name in IGNORE_NAMES or path.name.startswith(".env"):
            return True
        if extra_patterns:
            relative_str = path.relative_to(root).as_posix()
            for pattern in extra_patterns:
                if self._matches_gitignore(relative_str, path.name, pattern):
                    return True
        return False

    @staticmethod
    def _matches_gitignore(relative: str, name: str, pattern: str) -> bool:
        """Tiny subset of .gitignore matching: directory suffixes, name globs,
        and rooted paths. Good enough to ignore generated junk; doesn't handle
        negation, ``**``, or character classes — keep dependency-free."""
        pattern = pattern.strip()
        if not pattern or pattern.startswith("#"):
            return False
        # Directory pattern (foo/) — match any path under that dir.
        if pattern.endswith("/"):
            prefix = pattern.rstrip("/")
            return relative == prefix or relative.startswith(prefix + "/")
        # Rooted pattern (starts with /) → match against full relative path.
        if pattern.startswith("/"):
            anchored = pattern.lstrip("/")
            return fnmatch.fnmatch(relative, anchored) or relative.startswith(anchored + "/")
        # Plain name glob — match basename OR any path segment.
        if "/" not in pattern:
            return fnmatch.fnmatch(name, pattern) or any(
                fnmatch.fnmatch(segment, pattern)
                for segment in relative.split("/")
            )
        # Pattern with a slash — match against the full relative path.
        return fnmatch.fnmatch(relative, pattern) or relative.startswith(pattern + "/")

    def _parse_gitignore(self, root: Path) -> list[str]:
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        try:
            text = gitignore.read_text(errors="ignore")
        except OSError:
            return []
        patterns: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                # Negations (!pattern) are intentionally not honored — they'd
                # require a full ordered-rule engine. Conservative: skip them
                # so we don't accidentally include files the user wanted out.
                continue
            patterns.append(line)
        return patterns

    def _enumerate_paths(self, root: Path) -> list[Path]:
        # Prefer `git ls-files` for git repos: faster than walking and aligns
        # with what the repo owner considers tracked + untracked-but-not-ignored.
        if (root / ".git").exists():
            try:
                result = subprocess.run(
                    [
                        "git", "-C", str(root), "ls-files",
                        "--cached", "--others", "--exclude-standard",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0 and result.stdout:
                    out: list[Path] = []
                    for line in result.stdout.splitlines():
                        rel = line.strip()
                        if not rel:
                            continue
                        candidate = root / rel
                        if candidate.is_file():
                            out.append(candidate)
                    return sorted(out)
            except Exception:
                pass
        return sorted(root.rglob("*"))

    def _looks_binary(self, path: Path) -> bool:
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", "Makefile"}:
            return False
        try:
            chunk = path.read_bytes()[:1024]
        except OSError:
            return True
        return b"\x00" in chunk

    def _role(self, relative: str) -> RepoFileRole:
        lower = relative.lower()
        name = Path(relative).name.lower()
        if name in {"readme.md", "contributing.md"} or lower.startswith("docs/") or lower.endswith(".md"):
            return RepoFileRole.doc
        if "test" in lower or lower.endswith((".spec.ts", ".test.ts", ".spec.tsx", ".test.tsx", "_test.py")):
            return RepoFileRole.test
        if name in {"package.json", "pyproject.toml", "requirements.txt", "next.config.js", "tsconfig.json"} or lower.endswith((".config.js", ".config.ts", ".yml", ".yaml", ".toml")):
            return RepoFileRole.config
        if "/app/" in f"/{lower}" and ("page." in name or "route." in name):
            return RepoFileRole.route
        if "component" in lower or lower.endswith(".tsx"):
            return RepoFileRole.component
        if "model" in lower or "schema" in lower:
            return RepoFileRole.model
        if "service" in lower or "api" in lower:
            return RepoFileRole.service
        if name in {"main.py", "app.py", "index.ts", "index.tsx", "layout.tsx"}:
            return RepoFileRole.entrypoint
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")):
            return RepoFileRole.asset
        return RepoFileRole.unknown

    def _summarize_file(self, path: Path, relative: str, role: RepoFileRole) -> str:
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            return f"{role.value} file at {relative}."
        first_lines = [line.strip() for line in text.splitlines() if line.strip()][:4]
        return " ".join(first_lines)[:300] or f"{role.value} file at {relative}."

    def _hash_file(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def _detect_stack(self, root: Path):
        tech_stack: set[str] = set()
        package_managers: set[str] = set()
        frameworks: set[str] = set()
        test_commands: set[str] = set()
        build_commands: set[str] = set()
        lint_commands: set[str] = set()
        package_json = root / "package.json"
        if package_json.exists():
            tech_stack.add("Node.js")
            package_managers.add("npm")
            try:
                package = json.loads(package_json.read_text())
                deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
                scripts = package.get("scripts", {})
                if "next" in deps:
                    frameworks.add("Next.js")
                if "react" in deps:
                    frameworks.add("React")
                if "expo" in deps:
                    frameworks.add("Expo")
                if any(name.startswith("react-native") or name == "react-native" for name in deps):
                    frameworks.add("React Native")
                if any(name.startswith("@react-navigation/") for name in deps):
                    frameworks.add("React Navigation")
                if any(name.startswith("firebase") or name.startswith("@firebase/") for name in deps):
                    frameworks.add("Firebase")
                if "typescript" in deps or "typescript" in scripts:
                    tech_stack.add("TypeScript")
                for name, command in scripts.items():
                    if "test" in name:
                        test_commands.add(f"npm run {name}")
                    if "build" in name:
                        build_commands.add(f"npm run {name}")
                    if "lint" in name:
                        lint_commands.add(f"npm run {name}")
            except Exception:
                pass
        if (root / "pnpm-lock.yaml").exists():
            package_managers.add("pnpm")
        if (root / "yarn.lock").exists():
            package_managers.add("yarn")
        if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
            tech_stack.add("Python")
            test_commands.add("python -m pytest")
        if (root / "cto_os_api").exists():
            frameworks.add("FastAPI")
        return (
            sorted(tech_stack),
            sorted(package_managers),
            sorted(frameworks),
            sorted(test_commands),
            sorted(build_commands),
            sorted(lint_commands),
        )

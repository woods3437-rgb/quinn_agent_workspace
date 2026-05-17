"""Working Tree Intelligence (Phase 16.1).

Given a repository, produce a ``WorkingTreeSummary`` that tells the
operator what's changed since HEAD, grouped into clusters and tagged
with risks. Built on top of the Phase 16.5 ``FileClassifier`` so noise
is already known by the time we summarize.

Design constraints (locked in during the Phase 16 review):

- Rule-driven. No LLM, no semantic speculation. Every risk and every
  cluster maps to a concrete change pattern (a path shape, a file
  semantic type, or a line-count threshold).
- Evidence-backed. Every cluster and risk carries
  ``rules_triggered`` + human-readable ``evidence`` so the operator can
  verify exactly why each thing was flagged.
- Raw facts always available. The summary includes the full
  ``changed_files`` list, the ``noise_suppressed`` list (what was
  filtered + why), and the unvarnished ``raw_diff_stat`` output. The
  synthesized ``summary_lines`` are a convenience layer over those raw
  facts, never a replacement.
- Adaptive suggestions are intentionally OUT of scope here (deferred per
  the design review — avoid notification fatigue before the underlying
  detection is trustworthy). This module only describes the current
  state of the working tree; it does NOT tell the operator what to do.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .file_classifier import NOISE_TYPES, FileClassifier
from .models import (
    ChangedFile,
    ChangedFileStatus,
    ClassificationConfidence,
    DiffCluster,
    DiffClusterType,
    FileSemanticType,
    Repository,
    RiskKind,
    RiskSeverity,  # shared with Risk (low/medium/high/critical); WT never fires critical
    RiskyChange,
    WorkingTreeSummary,
)
from .repo_scanner import RepoScanner


# Files whose path matches any of these substrings are flagged as
# auth-adjacent. Conservative on purpose — we only fire when the
# segment clearly references identity / authn / authz.
_AUTH_PATH_SUBSTRINGS: tuple[str, ...] = (
    "auth/", "/auth.", "_auth.", "_auth/",
    "session/", "/session.", "_session.",
    "password", "passwd",
    "token/", "/token.", "_token.",
    "permission", "/role.", "/roles/", "/rbac/", "/acl/",
    "oauth", "credential", "secret",
    "/jwt.", "_jwt.",
)

# Per-file change above this many added+deleted lines is "large".
_LARGE_DIFF_LINE_THRESHOLD = 200

# Manifest filenames that go together with their lockfile sibling.
# Used by the dependency_bump / lockfile_only detectors.
_MANIFEST_TO_LOCKFILE: dict[str, tuple[str, ...]] = {
    "package.json": ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
    "pyproject.toml": ("uv.lock", "poetry.lock"),
    "requirements.txt": ("requirements.lock",),
    "Cargo.toml": ("Cargo.lock",),
    "Gemfile": ("Gemfile.lock",),
    "go.mod": ("go.sum",),
    "composer.json": ("composer.lock",),
    "Podfile": ("Podfile.lock",),
}
_LOCKFILE_TO_MANIFEST: dict[str, tuple[str, ...]] = {}
for _m, _locks in _MANIFEST_TO_LOCKFILE.items():
    for _lf in _locks:
        _LOCKFILE_TO_MANIFEST.setdefault(_lf, ())
        _LOCKFILE_TO_MANIFEST[_lf] = _LOCKFILE_TO_MANIFEST[_lf] + (_m,)


_STATUS_MAP = {
    "A": ChangedFileStatus.added,
    "M": ChangedFileStatus.modified,
    "D": ChangedFileStatus.deleted,
    "R": ChangedFileStatus.renamed,
    "C": ChangedFileStatus.copied,
    "?": ChangedFileStatus.untracked,
}


def evaluate_risks(changed: list[ChangedFile]) -> list[RiskyChange]:
    """Run every Phase 16.1 risk rule on a list of already-classified files.

    Pure / no I/O. Shared between :class:`WorkingTreeAnalyzer` (which
    feeds it live working-tree changes) and the Phase 16.4
    ``ReviewRouter`` (which feeds it changes parsed from a raw
    ``diff_text``). Same rules apply regardless of source.
    """
    if not changed:
        return []
    signal = [cf for cf in changed if not cf.is_noise]
    risks: list[RiskyChange] = []
    by_type: dict[FileSemanticType, list[ChangedFile]] = {}
    for cf in changed:
        by_type.setdefault(cf.semantic_type, []).append(cf)

    # migration_change — any file classified as migration.
    if FileSemanticType.migration in by_type:
        files = by_type[FileSemanticType.migration]
        risks.append(RiskyChange(
            kind=RiskKind.migration_change,
            severity=RiskSeverity.high,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in files],
            evidence=[f"Migration file present: {f.path}" for f in files],
            rules_triggered=["risk.migration_change"],
        ))

    # schema_change — schema file(s) modified (graphql / proto / prisma / openapi).
    if FileSemanticType.schema in by_type:
        files = by_type[FileSemanticType.schema]
        risks.append(RiskyChange(
            kind=RiskKind.schema_change,
            severity=RiskSeverity.high,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in files],
            evidence=[f"Schema file changed: {f.path}" for f in files],
            rules_triggered=["risk.schema_change"],
        ))

    # env_change — any .env* / secrets file touched.
    if FileSemanticType.env in by_type:
        files = by_type[FileSemanticType.env]
        risks.append(RiskyChange(
            kind=RiskKind.env_change,
            severity=RiskSeverity.high,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in files],
            evidence=[
                f"Environment / secrets file changed: {f.path}" for f in files
            ],
            rules_triggered=["risk.env_change"],
        ))

    # dependency_bump — manifest + lockfile both modified together.
    # lockfile_only_change — lockfile modified but no matching manifest.
    manifest_changes: list[str] = []
    lockfile_changes: list[str] = []
    for cf in changed:
        base = cf.path.rsplit("/", 1)[-1]
        if base in _MANIFEST_TO_LOCKFILE:
            manifest_changes.append(cf.path)
        if base in _LOCKFILE_TO_MANIFEST:
            lockfile_changes.append(cf.path)
    if manifest_changes and lockfile_changes:
        risks.append(RiskyChange(
            kind=RiskKind.dependency_bump,
            severity=RiskSeverity.low,
            confidence=ClassificationConfidence.high,
            files=sorted(set(manifest_changes + lockfile_changes)),
            evidence=[
                f"Manifest changed: {', '.join(manifest_changes)}",
                f"Lockfile changed: {', '.join(lockfile_changes)}",
            ],
            rules_triggered=["risk.dependency_bump"],
        ))
    elif lockfile_changes and not manifest_changes:
        risks.append(RiskyChange(
            kind=RiskKind.lockfile_only_change,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.high,
            files=lockfile_changes,
            evidence=[
                f"Lockfile {p} changed but its sibling manifest is not "
                f"in the working-tree diff." for p in lockfile_changes
            ],
            rules_triggered=["risk.lockfile_only_change"],
        ))

    # auth_path_touched — any changed path matches an auth substring.
    auth_files: list[str] = []
    for cf in changed:
        haystack = "/" + cf.path.lower()
        if any(needle in haystack for needle in _AUTH_PATH_SUBSTRINGS):
            auth_files.append(cf.path)
    if auth_files:
        risks.append(RiskyChange(
            kind=RiskKind.auth_path_touched,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.medium,
            files=auth_files,
            evidence=[f"Path looks auth-adjacent: {p}" for p in auth_files],
            rules_triggered=["risk.auth_path_touched"],
        ))

    # large_diff — single file with > threshold changes.
    big_files = [
        cf for cf in changed
        if (cf.added_lines + cf.deleted_lines) > _LARGE_DIFF_LINE_THRESHOLD
    ]
    if big_files:
        risks.append(RiskyChange(
            kind=RiskKind.large_diff,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in big_files],
            evidence=[
                f"{f.path}: +{f.added_lines} / -{f.deleted_lines} "
                f"(threshold {_LARGE_DIFF_LINE_THRESHOLD})"
                for f in big_files
            ],
            rules_triggered=["risk.large_diff"],
        ))

    # source_changed_without_test — at least one source file changed
    # and not a single test file is in the diff. Low-confidence hint.
    source_files = [cf for cf in signal if cf.semantic_type == FileSemanticType.source]
    test_files = [cf for cf in changed if cf.semantic_type == FileSemanticType.test]
    if source_files and not test_files:
        risks.append(RiskyChange(
            kind=RiskKind.source_changed_without_test,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.low,
            files=[f.path for f in source_files],
            evidence=[
                f"{len(source_files)} source file(s) changed; no test "
                f"files are in the working-tree diff.",
            ],
            rules_triggered=["risk.source_changed_without_test"],
        ))

    if FileSemanticType.infra in by_type:
        files = by_type[FileSemanticType.infra]
        risks.append(RiskyChange(
            kind=RiskKind.infra_change,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in files],
            evidence=[f"Infra config changed: {f.path}" for f in files],
            rules_triggered=["risk.infra_change"],
        ))

    if FileSemanticType.ci in by_type:
        files = by_type[FileSemanticType.ci]
        risks.append(RiskyChange(
            kind=RiskKind.ci_change,
            severity=RiskSeverity.medium,
            confidence=ClassificationConfidence.high,
            files=[f.path for f in files],
            evidence=[f"CI workflow changed: {f.path}" for f in files],
            rules_triggered=["risk.ci_change"],
        ))

    return risks


@dataclass
class WorkingTreeAnalyzer:
    """Stateless analyzer; safe to share across requests."""

    classifier: FileClassifier
    scanner: RepoScanner

    @classmethod
    def default(cls) -> "WorkingTreeAnalyzer":
        return cls(classifier=FileClassifier(), scanner=RepoScanner())

    # ------------------------------------------------------------ public

    def analyze(self, repository: Repository) -> WorkingTreeSummary:
        root = self.scanner.resolve_root(repository)
        branch = self._git(root, ["git", "branch", "--show-current"]).strip()
        raw_diff_stat = self._git(root, ["git", "diff", "--stat"], strip=False)
        changed = self._collect_changed_files(root)

        # Apply classification to every changed file. This gives downstream
        # consumers the noise flag and the rule evidence per file.
        for cf in changed:
            cls = self.classifier.classify(cf.path)
            cf.semantic_type = cls.semantic_type
            cf.classification_confidence = cls.confidence
            cf.classification_rules = list(cls.rules_triggered)
            cf.is_noise = cls.is_noise()

        signal = [cf for cf in changed if not cf.is_noise]
        noise = [cf for cf in changed if cf.is_noise]

        clusters: list[DiffCluster] = []
        clusters.extend(self._directory_clusters(signal))
        clusters.extend(self._semantic_clusters(signal))

        risks = self._risks(changed, signal)

        return WorkingTreeSummary(
            repository_id=repository.id,
            repository_path=str(root),
            current_branch=branch,
            changed_files=changed,
            clusters=clusters,
            risks=risks,
            noise_suppressed=noise,
            raw_diff_stat=raw_diff_stat,
            summary_lines=self._summary_lines(branch, changed, signal, noise, clusters, risks),
        )

    # ------------------------------------------------------------ collection

    def _collect_changed_files(self, root: Path) -> list[ChangedFile]:
        """Combine ``git status --porcelain`` (status + untracked) with
        ``git diff HEAD --numstat`` (added/deleted lines per tracked path).
        """
        # ``--untracked-files=all`` expands untracked subdirectories so the
        # caller sees every new file by path (vanilla ``--porcelain`` would
        # collapse a new ``src/`` directory to a single ``?? src/`` entry).
        porcelain = self._git(
            root,
            ["git", "status", "--porcelain", "--untracked-files=all"],
            strip=False,
        )
        numstat = self._git(root, ["git", "diff", "HEAD", "--numstat"], strip=False)

        # Numstat: lines like "12\t3\tpath" — "-" for binary.
        lines_by_path: dict[str, tuple[int, int]] = {}
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added_s, deleted_s, path = parts[0], parts[1], "\t".join(parts[2:])
            added = int(added_s) if added_s.isdigit() else 0
            deleted = int(deleted_s) if deleted_s.isdigit() else 0
            lines_by_path[path] = (added, deleted)

        out: list[ChangedFile] = []
        seen_paths: set[str] = set()
        for raw in porcelain.splitlines():
            if len(raw) < 4:
                continue
            xy = raw[:2]
            rest = raw[3:]
            # Renames: "R  old -> new" (with optional similarity score).
            if xy.startswith("R") or xy.startswith("C"):
                if " -> " in rest:
                    _, new_path = rest.split(" -> ", 1)
                else:
                    new_path = rest
                path = new_path.strip().strip('"')
                status = ChangedFileStatus.renamed if xy.startswith("R") else ChangedFileStatus.copied
            elif xy == "??":
                path = rest.strip().strip('"')
                status = ChangedFileStatus.untracked
            else:
                path = rest.strip().strip('"')
                primary = xy.strip()[:1] or xy[1:2]
                status = _STATUS_MAP.get(primary, ChangedFileStatus.unknown)

            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            added, deleted = lines_by_path.get(path, (0, 0))
            out.append(ChangedFile(
                path=path,
                status=status,
                added_lines=added,
                deleted_lines=deleted,
            ))
        return out

    # ------------------------------------------------------------ clustering

    @staticmethod
    def _directory_clusters(signal: list[ChangedFile]) -> list[DiffCluster]:
        """Group changed signal files by their direct parent directory.

        Also emit a higher-level ancestor cluster when 3+ files share the
        same 1- or 2-segment prefix across multiple subdirectories (so
        ``src/auth/{handlers,services,types}/...`` shows up as a single
        ``src/auth/`` cluster instead of three tiny leaves).
        """
        if not signal:
            return []
        by_dir: dict[str, list[ChangedFile]] = {}
        for cf in signal:
            parent = cf.path.rsplit("/", 1)[0] if "/" in cf.path else "."
            by_dir.setdefault(parent, []).append(cf)

        clusters: list[DiffCluster] = []
        leaf_dirs: set[str] = set()
        for parent, group in sorted(by_dir.items()):
            if len(group) >= 2:
                leaf_dirs.add(parent)
                clusters.append(DiffCluster(
                    name=(parent + "/") if parent != "." else "(root)",
                    cluster_type=DiffClusterType.directory,
                    files=[f.path for f in group],
                    rules_triggered=["cluster.directory-leaf"],
                    confidence=ClassificationConfidence.high if len(group) >= 3
                    else ClassificationConfidence.medium,
                    evidence=[
                        f"{len(group)} non-noise files share parent directory {parent}/",
                    ],
                ))

        # Ancestor groups (1- and 2-segment prefixes) — only emit if they
        # cover multiple distinct subdirs and aren't already a leaf.
        ancestor_groups: dict[str, list[ChangedFile]] = {}
        for cf in signal:
            parts = cf.path.split("/")
            for depth in (1, 2):
                if len(parts) > depth:
                    ancestor = "/".join(parts[:depth])
                    ancestor_groups.setdefault(ancestor, []).append(cf)
        for ancestor, group in sorted(ancestor_groups.items()):
            if len(group) < 3:
                continue
            subdirs = {f.path.rsplit("/", 1)[0] for f in group}
            if len(subdirs) < 2:
                continue
            if ancestor in leaf_dirs:
                continue
            clusters.append(DiffCluster(
                name=ancestor + "/",
                cluster_type=DiffClusterType.directory,
                files=[f.path for f in group],
                rules_triggered=["cluster.directory-ancestor"],
                confidence=ClassificationConfidence.medium,
                evidence=[
                    f"{len(group)} files under {ancestor}/ spanning "
                    f"{len(subdirs)} subdirectories",
                ],
            ))
        return clusters

    @staticmethod
    def _semantic_clusters(signal: list[ChangedFile]) -> list[DiffCluster]:
        """Group by semantic type for high-signal categories.

        We only emit semantic clusters for types where seeing the group
        is operationally useful (migrations / schemas / configs / env /
        ci / infra). ``source`` and ``test`` files are dominated by
        directory clusters; emitting them again here would just be noise.
        """
        interesting = {
            FileSemanticType.migration,
            FileSemanticType.schema,
            FileSemanticType.env,
            FileSemanticType.config,
            FileSemanticType.ci,
            FileSemanticType.infra,
        }
        by_type: dict[FileSemanticType, list[ChangedFile]] = {}
        for cf in signal:
            if cf.semantic_type in interesting:
                by_type.setdefault(cf.semantic_type, []).append(cf)

        out: list[DiffCluster] = []
        for type_, group in by_type.items():
            out.append(DiffCluster(
                name=type_.value,
                cluster_type=DiffClusterType.semantic,
                files=[f.path for f in group],
                rules_triggered=[f"cluster.semantic.{type_.value}"],
                confidence=ClassificationConfidence.high,
                evidence=[
                    f"{len(group)} file(s) classified as {type_.value}",
                ],
            ))
        return out

    # ------------------------------------------------------------ risk rules

    def _risks(
        self,
        changed: list[ChangedFile],
        signal: list[ChangedFile],
    ) -> list[RiskyChange]:
        # Phase 16.4: rules live at module level so the review router
        # can reuse them on a parsed diff_text without needing a real
        # repository (or even an analyzer instance).
        return evaluate_risks(changed)

    # ------------------------------------------------------------ summary

    @staticmethod
    def _summary_lines(
        branch: str,
        changed: list[ChangedFile],
        signal: list[ChangedFile],
        noise: list[ChangedFile],
        clusters: list[DiffCluster],
        risks: list[RiskyChange],
    ) -> list[str]:
        """Plain-text bullets for human consumption.

        Intentionally factual: "5 files changed, 1 suppressed as noise".
        Never speculative. The raw lists are still available on the
        summary so an operator can drill in.
        """
        if not changed:
            return ["Working tree clean."]
        out: list[str] = []
        out.append(
            f"Branch: {branch or '(detached HEAD)'} — "
            f"{len(changed)} changed file(s) "
            f"({len(signal)} signal, {len(noise)} suppressed as noise)."
        )
        if clusters:
            top = clusters[:5]
            for c in top:
                out.append(
                    f"Cluster [{c.cluster_type.value}/{c.confidence.value}] "
                    f"{c.name}: {len(c.files)} file(s)"
                )
        if risks:
            for r in risks:
                out.append(
                    f"Risk [{r.kind.value}/{r.severity.value}/"
                    f"{r.confidence.value}]: {len(r.files)} file(s)"
                )
        if noise:
            out.append(
                f"Suppressed (raw list available): "
                f"{', '.join(sorted(f.path for f in noise)[:5])}"
                + ("…" if len(noise) > 5 else "")
            )
        return out

    # ------------------------------------------------------------ git helper

    @staticmethod
    def _git(cwd: Path, args: list[str], strip: bool = True) -> str:
        try:
            result = subprocess.run(
                args, cwd=cwd, check=False, capture_output=True,
                text=True, timeout=10,
            )
        except Exception as exc:
            return str(exc)
        output = result.stdout if result.stdout else result.stderr
        return output.strip() if strip else output.rstrip("\n")

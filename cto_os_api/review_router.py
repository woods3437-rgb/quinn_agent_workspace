"""Real Review Routing (Phase 16.4).

Picks a code-review intensity from the rules already established in
16.5 (file semantic classifier) and 16.1 (working-tree risk evaluator).
This module adds NO new classifications; it only routes.

Design constraints (locked in by the Phase 16 review):

- Every routing decision exposes selected_intensity, recommended_intensity
  (what the router would have chosen pre-override), confidence,
  rules_triggered, evidence, risks_considered, and routes_considered.
- The working-tree summary that informed the decision is referenced (or
  embedded) on the result so the operator can drill into raw facts.
- Rule-driven only. No LLM, no inferred intent, no adaptive suggestions.
- Read-only. The MCP tool (``route_review``) lives outside
  ``WRITE_TOOL_NAMES``; this module never writes git, never opens PRs,
  never executes shell directly (it goes through GitReader /
  WorkingTreeAnalyzer).

Routing rules (spec from the Phase 16.4 brief):

    migration_change             → migration
    schema_change                → migration  (priority order absorbs "or full")
    env_change                   → security
    auth_path_touched            → security
    dependency_bump              → dependency
    lockfile_only_change         → dependency
    infra_change                 → config
    ci_change                    → config
    (all signal files are docs)  → docs_only
    source_changed_without_test  → full        (confidence: low)
    large_diff                   → full
    (nothing else fires)         → lightweight

When multiple rules fire, the highest-priority intensity wins:

    security > migration > dependency > config > full > lightweight > docs_only

All fired rules remain in ``rules_triggered`` and ``routes_considered`` so
the operator can audit the call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .file_classifier import FileClassifier
from .models import (
    ChangedFile,
    ChangedFileStatus,
    ClassificationConfidence,
    FileSemanticType,
    Repository,
    ReviewIntensity,
    ReviewRoute,
    ReviewRoutingResult,
    RiskKind,
    RiskyChange,
    WorkingTreeSummary,
)
from .working_tree import WorkingTreeAnalyzer, evaluate_risks


# ----------------------------------------------------------------- rule table


@dataclass(frozen=True)
class _Rule:
    """Internal rule definition. Each maps a fired risk (or a non-risk
    predicate) to a recommended ReviewIntensity and the confidence of
    that recommendation. Rule name is the public identifier that ends
    up in ``rules_triggered``.
    """

    name: str
    intensity: ReviewIntensity
    confidence: ClassificationConfidence
    description: str


# Risk-driven rules. Spec: every named RiskKind has a defined route.
_RISK_TO_RULE: dict[RiskKind, _Rule] = {
    RiskKind.env_change: _Rule(
        "route.env_change->security",
        ReviewIntensity.security, ClassificationConfidence.high,
        "Env / secrets file changed",
    ),
    RiskKind.auth_path_touched: _Rule(
        "route.auth_path_touched->security",
        # Confidence is medium because auth_path_touched itself is a
        # medium-confidence (path-based heuristic) risk.
        ReviewIntensity.security, ClassificationConfidence.medium,
        "Auth-adjacent path changed",
    ),
    RiskKind.migration_change: _Rule(
        "route.migration_change->migration",
        ReviewIntensity.migration, ClassificationConfidence.high,
        "Migration file present",
    ),
    RiskKind.schema_change: _Rule(
        "route.schema_change->migration",
        ReviewIntensity.migration, ClassificationConfidence.high,
        "Schema file changed (Prisma / proto / GraphQL / OpenAPI)",
    ),
    RiskKind.dependency_bump: _Rule(
        "route.dependency_bump->dependency",
        ReviewIntensity.dependency, ClassificationConfidence.high,
        "Manifest + lockfile both changed",
    ),
    RiskKind.lockfile_only_change: _Rule(
        "route.lockfile_only_change->dependency",
        ReviewIntensity.dependency, ClassificationConfidence.high,
        "Lockfile changed without manifest",
    ),
    RiskKind.infra_change: _Rule(
        "route.infra_change->config",
        ReviewIntensity.config, ClassificationConfidence.high,
        "Dockerfile / compose / terraform / k8s changed",
    ),
    RiskKind.ci_change: _Rule(
        "route.ci_change->config",
        ReviewIntensity.config, ClassificationConfidence.high,
        "CI workflow file changed",
    ),
    RiskKind.large_diff: _Rule(
        "route.large_diff->full",
        ReviewIntensity.full, ClassificationConfidence.high,
        "Large diff (>200 lines in a single file)",
    ),
    RiskKind.source_changed_without_test: _Rule(
        "route.source_changed_without_test->full",
        # Per spec: route to full review at LOW confidence — this is a
        # hint, not a verdict.
        ReviewIntensity.full, ClassificationConfidence.low,
        "Source changed but no test files in the diff",
    ),
}


# Priority order. Highest-risk-and-most-specific first; ``lightweight``
# is the fallback when nothing else fires; ``docs_only`` is intentionally
# the lowest priority so that ANY other firing route preempts it.
_INTENSITY_PRIORITY: tuple[ReviewIntensity, ...] = (
    ReviewIntensity.security,
    ReviewIntensity.migration,
    ReviewIntensity.dependency,
    ReviewIntensity.config,
    ReviewIntensity.full,
    ReviewIntensity.lightweight,
    ReviewIntensity.docs_only,
)


# ---------------------------------------------------------------- diff parser


def _parse_unified_diff(text: str) -> list[tuple[str, ChangedFileStatus, int, int]]:
    """Extract ``(path, status, added_lines, deleted_lines)`` per file
    from a unified diff. Counts ``+`` and ``-`` body lines (skipping the
    ``+++`` / ``---`` headers). Renames produce a single entry under the
    new path with status=``R``.

    Pure / no I/O. Tolerant of partial diffs (missing headers etc.).
    """
    if not text:
        return []
    out: list[tuple[str, ChangedFileStatus, int, int]] = []
    current_path: str | None = None
    current_status = ChangedFileStatus.modified
    added = 0
    deleted = 0

    def _flush() -> None:
        nonlocal current_path, current_status, added, deleted
        if current_path is not None:
            out.append((current_path, current_status, added, deleted))
        current_path = None
        current_status = ChangedFileStatus.modified
        added = 0
        deleted = 0

    for raw in text.splitlines():
        if raw.startswith("diff --git"):
            _flush()
            parts = raw.split()
            if len(parts) >= 4:
                a_path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
                b_path = parts[3][2:] if parts[3].startswith("b/") else parts[3]
                current_path = b_path or a_path
                if a_path and b_path and a_path != b_path:
                    current_status = ChangedFileStatus.renamed
        elif raw.startswith("new file mode"):
            current_status = ChangedFileStatus.added
        elif raw.startswith("deleted file mode"):
            current_status = ChangedFileStatus.deleted
        elif raw.startswith("rename from") or raw.startswith("rename to"):
            current_status = ChangedFileStatus.renamed
        elif raw.startswith("copy from") or raw.startswith("copy to"):
            current_status = ChangedFileStatus.copied
        elif raw.startswith("+++") or raw.startswith("---"):
            continue
        elif raw.startswith("+"):
            added += 1
        elif raw.startswith("-"):
            deleted += 1
    _flush()
    return out


# --------------------------------------------------------------- router class


@dataclass
class ReviewRouter:
    """Stateless router — safe to construct per-call."""

    classifier: FileClassifier = field(default_factory=FileClassifier)
    analyzer: WorkingTreeAnalyzer = field(default_factory=WorkingTreeAnalyzer.default)

    # -------------------------------------------------- public entrypoints

    def route_from_working_tree(
        self,
        repository: Repository,
        intensity_override: ReviewIntensity | None = None,
        include_working_tree_summary: bool = True,
    ) -> ReviewRoutingResult:
        summary = self.analyzer.analyze(repository)
        return self._route(
            changed_files=summary.changed_files,
            risks=summary.risks,
            working_tree_summary=summary if include_working_tree_summary else None,
            diff_source="working_tree",
            intensity_override=intensity_override,
        )

    def route_from_diff_text(
        self,
        diff_text: str,
        intensity_override: ReviewIntensity | None = None,
    ) -> ReviewRoutingResult:
        changed = self._changed_files_from_diff(diff_text)
        risks = evaluate_risks(changed)
        return self._route(
            changed_files=changed,
            risks=risks,
            working_tree_summary=None,
            diff_source="diff_text",
            intensity_override=intensity_override,
        )

    # ------------------------------------------------------------ internals

    def _changed_files_from_diff(self, diff_text: str) -> list[ChangedFile]:
        out: list[ChangedFile] = []
        for path, status, added, deleted in _parse_unified_diff(diff_text):
            cls = self.classifier.classify(path)
            out.append(ChangedFile(
                path=path,
                status=status,
                added_lines=added,
                deleted_lines=deleted,
                semantic_type=cls.semantic_type,
                classification_confidence=cls.confidence,
                classification_rules=list(cls.rules_triggered),
                is_noise=cls.is_noise(),
            ))
        return out

    def _route(
        self,
        changed_files: list[ChangedFile],
        risks: list[RiskyChange],
        working_tree_summary: WorkingTreeSummary | None,
        diff_source: str,
        intensity_override: ReviewIntensity | None,
    ) -> ReviewRoutingResult:
        routes = self._fire_routes(changed_files, risks)
        # If nothing fired, synthesize a default-lightweight route so the
        # audit trail (rules_triggered + routes_considered) stays
        # consistent: every routing decision has at least one named rule
        # behind it, even the fallback.
        if not routes:
            routes = [self._default_lightweight_route(changed_files)]
        recommended, recommended_confidence, evidence = self._select_intensity(routes)
        selected = recommended
        override_applied = False
        if intensity_override is not None and intensity_override != recommended:
            selected = intensity_override
            override_applied = True
            evidence = evidence + [
                f"Operator override applied: routing to {intensity_override.value} "
                f"instead of recommended {recommended.value}.",
            ]
        return ReviewRoutingResult(
            selected_intensity=selected,
            recommended_intensity=recommended,
            confidence=recommended_confidence,
            rules_triggered=[r.rule_name for r in routes],
            evidence=evidence,
            risks_considered=[r.kind for r in risks],
            routes_considered=routes,
            override_applied=override_applied,
            diff_source=diff_source,
            working_tree_summary=working_tree_summary,
        )

    @staticmethod
    def _default_lightweight_route(
        changed_files: list[ChangedFile],
    ) -> ReviewRoute:
        if not changed_files:
            evidence = ["Working tree is clean — no review needed."]
            confidence = ClassificationConfidence.high
        else:
            evidence = [
                "No high-signal risk or rule fired; defaulting to lightweight review.",
            ]
            confidence = ClassificationConfidence.medium
        return ReviewRoute(
            rule_name="route.default-lightweight",
            intensity=ReviewIntensity.lightweight,
            confidence=confidence,
            evidence=evidence,
        )

    def _fire_routes(
        self,
        changed_files: list[ChangedFile],
        risks: list[RiskyChange],
    ) -> list[ReviewRoute]:
        routes: list[ReviewRoute] = []

        # 1) Every risk produces its mapped route (if defined).
        for risk in risks:
            rule = _RISK_TO_RULE.get(risk.kind)
            if rule is None:
                continue
            routes.append(ReviewRoute(
                rule_name=rule.name,
                intensity=rule.intensity,
                confidence=rule.confidence,
                evidence=[rule.description] + list(risk.evidence),
            ))

        # 2) docs_only — fires when every non-noise changed file is docs.
        #    Skipped when nothing changed (then we fall through to the
        #    default lightweight at selection time).
        signal = [cf for cf in changed_files if not cf.is_noise]
        if signal and all(cf.semantic_type == FileSemanticType.docs for cf in signal):
            routes.append(ReviewRoute(
                rule_name="route.docs_only",
                intensity=ReviewIntensity.docs_only,
                confidence=ClassificationConfidence.high,
                evidence=[
                    f"All {len(signal)} non-noise changed file(s) classified as docs",
                ],
            ))

        return routes

    @staticmethod
    def _select_intensity(
        routes: list[ReviewRoute],
    ) -> tuple[ReviewIntensity, ClassificationConfidence, list[str]]:
        """Pick the highest-priority intensity. Caller guarantees that
        ``routes`` has at least one entry (the default-lightweight route
        is synthesized upstream when no rule fired).

        Evidence is gathered from EVERY fired route, not just the winner,
        so the operator sees the full picture rather than a single
        synthesized line.
        """
        sorted_routes = sorted(
            routes, key=lambda r: _INTENSITY_PRIORITY.index(r.intensity)
        )
        winner = sorted_routes[0]
        evidence: list[str] = []
        for r in routes:
            evidence.append(
                f"[{r.rule_name} -> {r.intensity.value} "
                f"(confidence={r.confidence.value})]"
            )
            evidence.extend(r.evidence)
        return winner.intensity, winner.confidence, evidence

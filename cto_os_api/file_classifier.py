"""File semantic classifier (Phase 16.5 — Noise Suppression).

Foundational layer for working-tree summaries, candidate-file ranking,
review routing, and resume-work. Tells the rest of the system whether a
given path is actual source code, a config file we care about, a
migration that warrants extra review, or noise we should suppress by
default (lockfiles, generated code, vendored deps, snapshots, build
artifacts).

Phase 16 design constraints (carried forward verbatim):

- Evidence-backed. Every classification carries ``rules_triggered`` so
  the operator can see exactly which rule(s) fired.
- Rule-driven, no LLM. Pure string + path matching against well-known
  conventions. Stay grounded; no semantic speculation.
- Noise suppression is opt-out, not opt-in. Lockfiles / generated /
  vendored / snapshots / build artifacts are ``NOISE_TYPES`` and are
  excluded from summaries, candidate files, branch plans, and reviews
  by default. The operator can still surface a noisy file by naming it
  explicitly (handled in the candidate-files filename-hint path).
- Raw facts always available. ``MCPToolset.classify_repo_files`` returns
  every file with its full classification, so a "what got filtered and
  why" view is always reachable without re-running the scanner.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum


class FileSemanticType(str, Enum):
    """What kind of file is this, operationally?

    Categories are designed to drive concrete behavior:
    - ``source`` / ``test``: the operator's actual work surface.
    - ``config`` / ``schema`` / ``migration`` / ``env`` / ``ci`` /
      ``infra``: high-signal changes that often warrant heavier review.
    - ``docs`` / ``asset``: low-risk but should remain visible.
    - ``lockfile`` / ``generated`` / ``vendored`` / ``snapshot`` /
      ``build_artifact``: noise; suppress by default in summaries and
      candidate selection.
    - ``unknown``: classifier had no rule and no recognized extension.
    """

    source = "source"
    test = "test"
    config = "config"
    schema = "schema"
    migration = "migration"
    docs = "docs"
    lockfile = "lockfile"
    generated = "generated"
    vendored = "vendored"
    snapshot = "snapshot"
    build_artifact = "build_artifact"
    env = "env"
    ci = "ci"
    infra = "infra"
    asset = "asset"
    unknown = "unknown"


class ClassificationConfidence(str, Enum):
    """How sure we are about the classification.

    - ``high``: exact filename or unambiguous directory rule.
    - ``medium``: path-shape match (e.g. ``*/migrations/*``); plausibly
      could be wrong on an unusual layout.
    - ``low``: no rule fired and we defaulted by extension, or no
      extension match either.
    """

    low = "low"
    medium = "medium"
    high = "high"


NOISE_TYPES: frozenset[FileSemanticType] = frozenset({
    FileSemanticType.lockfile,
    FileSemanticType.generated,
    FileSemanticType.vendored,
    FileSemanticType.snapshot,
    FileSemanticType.build_artifact,
})


@dataclass(frozen=True)
class FileClassification:
    """Result of classifying one file path. Frozen / hashable / pure."""

    path: str
    semantic_type: FileSemanticType
    confidence: ClassificationConfidence
    rules_triggered: tuple[str, ...] = field(default_factory=tuple)

    def is_noise(self) -> bool:
        return self.semantic_type in NOISE_TYPES

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "semantic_type": self.semantic_type.value,
            "confidence": self.confidence.value,
            "rules_triggered": list(self.rules_triggered),
        }


def is_noise(classification: FileClassification) -> bool:
    """Convenience for call sites that hold a classification object."""
    return classification.is_noise()


# ---------------------------------------------------------------- rules
#
# Each rule is a pure-data record describing one match pattern. The
# classifier runs every rule and collects each match into
# ``rules_triggered``; the *primary* type is taken from the first rule
# that fired, so order in this table is significant. Group ordering
# (lockfiles first → vendored → build artifacts → snapshots → generated
# → schema/migration/env/ci/infra/config → tests → docs → assets) keeps
# the most-specific, highest-confidence classifications first.


@dataclass(frozen=True)
class _Rule:
    name: str
    semantic_type: FileSemanticType
    confidence: ClassificationConfidence
    exact_name: tuple[str, ...] = ()
    name_globs: tuple[str, ...] = ()
    path_globs: tuple[str, ...] = ()
    path_contains: tuple[str, ...] = ()
    path_starts_with: tuple[str, ...] = ()
    extension: tuple[str, ...] = ()

    def matches(self, path: str, name: str, lower_path: str, lower_name: str) -> bool:
        if self.exact_name and name in self.exact_name:
            return True
        if self.name_globs and any(
            fnmatch.fnmatch(lower_name, glob.lower()) for glob in self.name_globs
        ):
            return True
        if self.path_globs and any(
            fnmatch.fnmatch(lower_path, glob.lower()) for glob in self.path_globs
        ):
            return True
        if self.path_contains and any(needle in lower_path for needle in self.path_contains):
            return True
        if self.path_starts_with and any(
            lower_path.startswith(prefix) for prefix in self.path_starts_with
        ):
            return True
        if self.extension:
            ext = ""
            if "." in lower_name:
                ext = "." + lower_name.rsplit(".", 1)[-1]
            if ext in self.extension:
                return True
        return False


_CODE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".rb", ".java", ".kt", ".swift",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".m", ".mm",
    ".cs", ".php", ".dart", ".scala", ".clj", ".ex", ".exs", ".erl",
    ".sh", ".bash", ".zsh",
})


_RULES: tuple[_Rule, ...] = (
    # ----------------------------------------------------------- lockfiles
    _Rule("lockfile.npm-package-lock", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("package-lock.json",)),
    _Rule("lockfile.yarn", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("yarn.lock",)),
    _Rule("lockfile.pnpm", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("pnpm-lock.yaml",)),
    _Rule("lockfile.python", FileSemanticType.lockfile,
          ClassificationConfidence.high,
          exact_name=("Pipfile.lock", "poetry.lock", "uv.lock", "requirements.lock")),
    _Rule("lockfile.rust", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("Cargo.lock",)),
    _Rule("lockfile.go", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("go.sum",)),
    _Rule("lockfile.ruby", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("Gemfile.lock",)),
    _Rule("lockfile.composer", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("composer.lock",)),
    _Rule("lockfile.cocoapods", FileSemanticType.lockfile,
          ClassificationConfidence.high, exact_name=("Podfile.lock",)),

    # ----------------------------------------------------------- vendored
    _Rule("vendored.node_modules", FileSemanticType.vendored,
          ClassificationConfidence.high, path_contains=("node_modules/",)),
    _Rule("vendored.vendor-dir", FileSemanticType.vendored,
          ClassificationConfidence.high,
          path_starts_with=("vendor/", "third_party/"),
          path_contains=("/vendor/", "/third_party/")),
    _Rule("vendored.cocoapods", FileSemanticType.vendored,
          ClassificationConfidence.high,
          path_starts_with=("pods/", "ios/pods/", "macos/pods/"),
          path_contains=("/pods/",)),
    _Rule("vendored.gradle-wrapper", FileSemanticType.vendored,
          ClassificationConfidence.high, path_contains=("gradle/wrapper/",)),
    _Rule("vendored.python-site-packages", FileSemanticType.vendored,
          ClassificationConfidence.high, path_contains=("site-packages/",)),

    # ----------------------------------------------------------- build artifacts
    _Rule("build_artifact.js-output", FileSemanticType.build_artifact,
          ClassificationConfidence.high,
          path_starts_with=("dist/", "build/", "out/", ".next/", ".nuxt/",
                            ".vercel/", ".turbo/", ".cache/", ".parcel-cache/",
                            ".rollup.cache/", ".swc/"),
          path_contains=("/dist/", "/build/", "/out/", "/.next/", "/.turbo/")),
    _Rule("build_artifact.expo", FileSemanticType.build_artifact,
          ClassificationConfidence.high,
          path_starts_with=(".expo/", ".expo-shared/", ".metro-cache/")),
    _Rule("build_artifact.coverage", FileSemanticType.build_artifact,
          ClassificationConfidence.high,
          path_starts_with=("coverage/",), path_contains=("/coverage/",)),
    _Rule("build_artifact.ios-derived", FileSemanticType.build_artifact,
          ClassificationConfidence.high,
          path_contains=("deriveddata/", "/build/products/", "ios/build/")),
    _Rule("build_artifact.android-build", FileSemanticType.build_artifact,
          ClassificationConfidence.high,
          path_contains=("android/build/", "android/app/build/", ".gradle/")),
    _Rule("build_artifact.target", FileSemanticType.build_artifact,
          ClassificationConfidence.high, path_starts_with=("target/",)),
    _Rule("build_artifact.pycache", FileSemanticType.build_artifact,
          ClassificationConfidence.high, path_contains=("__pycache__/",)),

    # ----------------------------------------------------------- snapshots
    _Rule("snapshot.jest", FileSemanticType.snapshot,
          ClassificationConfidence.high, path_contains=("__snapshots__/",)),
    _Rule("snapshot.snap-ext", FileSemanticType.snapshot,
          ClassificationConfidence.high, extension=(".snap",)),
    _Rule("snapshot.image", FileSemanticType.snapshot,
          ClassificationConfidence.medium,
          name_globs=("*.snapshot.png", "*.snapshot.jpg", "*-snapshot.png")),

    # ----------------------------------------------------------- generated
    _Rule("generated.protobuf", FileSemanticType.generated,
          ClassificationConfidence.high,
          name_globs=("*.pb.go", "*.pb.ts", "*.pb.py",
                      "*_pb2.py", "*_pb2_grpc.py")),
    _Rule("generated.dot-generated", FileSemanticType.generated,
          ClassificationConfidence.high,
          name_globs=("*.generated.*", "*_generated.go", "*.gen.go",
                      "*.gen.ts", "*.g.dart", "*.freezed.dart")),
    _Rule("generated.prisma-client", FileSemanticType.generated,
          ClassificationConfidence.high,
          path_starts_with=("generated/prisma/", ".prisma/client/"),
          path_contains=("/generated/prisma/", "/.prisma/client/")),
    _Rule("generated.graphql-codegen", FileSemanticType.generated,
          ClassificationConfidence.medium,
          name_globs=("*.graphql.ts", "graphql.generated.ts",
                      "schema.generated.*")),
    _Rule("generated.under-generated-dir", FileSemanticType.generated,
          ClassificationConfidence.medium,
          path_starts_with=("__generated__/", ".generated/"),
          path_contains=("/__generated__/", "/.generated/")),

    # ----------------------------------------------------------- schema
    _Rule("schema.prisma", FileSemanticType.schema,
          ClassificationConfidence.high, exact_name=("schema.prisma",)),
    _Rule("schema.openapi", FileSemanticType.schema,
          ClassificationConfidence.high,
          name_globs=("openapi.yaml", "openapi.yml", "openapi.json",
                      "swagger.yaml", "swagger.yml", "swagger.json")),
    _Rule("schema.proto", FileSemanticType.schema,
          ClassificationConfidence.high, extension=(".proto",)),
    _Rule("schema.graphql", FileSemanticType.schema,
          ClassificationConfidence.high, extension=(".graphql", ".gql")),

    # ----------------------------------------------------------- migration
    _Rule("migration.prisma", FileSemanticType.migration,
          ClassificationConfidence.high,
          path_contains=("prisma/migrations/",)),
    _Rule("migration.rails", FileSemanticType.migration,
          ClassificationConfidence.high, path_starts_with=("db/migrate/",)),
    _Rule("migration.alembic", FileSemanticType.migration,
          ClassificationConfidence.high,
          path_contains=("alembic/versions/",)),
    _Rule("migration.directory", FileSemanticType.migration,
          ClassificationConfidence.medium,
          path_contains=("/migrations/", "/migrate/")),

    # ----------------------------------------------------------- env
    _Rule("env.dotenv", FileSemanticType.env,
          ClassificationConfidence.high, name_globs=(".env", ".env.*")),
    _Rule("env.secrets", FileSemanticType.env,
          ClassificationConfidence.high,
          exact_name=("secrets.json", "secrets.yaml", "secrets.yml")),

    # ----------------------------------------------------------- ci
    _Rule("ci.github-actions", FileSemanticType.ci,
          ClassificationConfidence.high,
          path_starts_with=(".github/workflows/",)),
    _Rule("ci.gitlab", FileSemanticType.ci,
          ClassificationConfidence.high, exact_name=(".gitlab-ci.yml",)),
    _Rule("ci.circleci", FileSemanticType.ci,
          ClassificationConfidence.high, path_starts_with=(".circleci/",)),
    _Rule("ci.travis", FileSemanticType.ci,
          ClassificationConfidence.high, exact_name=(".travis.yml",)),
    _Rule("ci.buildkite", FileSemanticType.ci,
          ClassificationConfidence.high, path_starts_with=(".buildkite/",)),

    # ----------------------------------------------------------- infra
    _Rule("infra.dockerfile", FileSemanticType.infra,
          ClassificationConfidence.high,
          name_globs=("Dockerfile", "Dockerfile.*", "*.Dockerfile",
                      "dockerfile", "dockerfile.*")),
    _Rule("infra.docker-compose", FileSemanticType.infra,
          ClassificationConfidence.high,
          name_globs=("docker-compose.yml", "docker-compose.yaml",
                      "docker-compose.*.yml", "docker-compose.*.yaml")),
    _Rule("infra.terraform", FileSemanticType.infra,
          ClassificationConfidence.high, extension=(".tf", ".tfvars")),
    _Rule("infra.k8s", FileSemanticType.infra,
          ClassificationConfidence.medium,
          path_starts_with=("k8s/", "kubernetes/", "deploy/k8s/",
                            "helm/", "charts/")),

    # ----------------------------------------------------------- config
    _Rule("config.package-json", FileSemanticType.config,
          ClassificationConfidence.high, exact_name=("package.json",)),
    _Rule("config.tsconfig", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=("tsconfig.json", "tsconfig.*.json")),
    _Rule("config.pyproject", FileSemanticType.config,
          ClassificationConfidence.high,
          exact_name=("pyproject.toml", "setup.cfg", "setup.py",
                      "requirements.txt", "Pipfile")),
    _Rule("config.next", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=("next.config.js", "next.config.mjs", "next.config.ts")),
    _Rule("config.vercel", FileSemanticType.config,
          ClassificationConfidence.high, exact_name=("vercel.json",)),
    _Rule("config.expo-app", FileSemanticType.config,
          ClassificationConfidence.high,
          exact_name=("app.json", "app.config.js", "app.config.ts",
                      "expo.json", "metro.config.js")),
    _Rule("config.firebase", FileSemanticType.config,
          ClassificationConfidence.high,
          exact_name=("firebase.json", "firestore.rules",
                      "firestore.indexes.json", "storage.rules")),
    _Rule("config.jest", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=("jest.config.js", "jest.config.ts",
                      "jest.setup.js", "jest.setup.ts")),
    _Rule("config.eslint", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=(".eslintrc", ".eslintrc.*", "eslint.config.*")),
    _Rule("config.prettier", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=(".prettierrc", ".prettierrc.*", "prettier.config.*")),
    _Rule("config.babel", FileSemanticType.config,
          ClassificationConfidence.high,
          name_globs=("babel.config.js", "babel.config.json",
                      ".babelrc", ".babelrc.*")),
    _Rule("config.misc-dot-config", FileSemanticType.config,
          ClassificationConfidence.medium,
          name_globs=("*.config.js", "*.config.ts",
                      "*.config.mjs", "*.config.cjs")),

    # ----------------------------------------------------------- tests
    _Rule("test.spec-or-test-suffix", FileSemanticType.test,
          ClassificationConfidence.high,
          name_globs=("*.test.ts", "*.test.tsx", "*.test.js", "*.test.jsx",
                      "*.spec.ts", "*.spec.tsx", "*.spec.js", "*.spec.jsx",
                      "*_test.py", "test_*.py", "*_spec.rb", "*_test.go")),
    _Rule("test.directory", FileSemanticType.test,
          ClassificationConfidence.medium,
          path_contains=("/tests/", "/__tests__/", "/spec/")),
    _Rule("test.top-tests-dir", FileSemanticType.test,
          ClassificationConfidence.medium,
          path_starts_with=("tests/", "test/")),

    # ----------------------------------------------------------- docs
    _Rule("docs.readme-and-friends", FileSemanticType.docs,
          ClassificationConfidence.high,
          exact_name=("README.md", "README.rst", "README.txt",
                      "CONTRIBUTING.md", "CHANGELOG.md", "CHANGELOG.rst",
                      "LICENSE", "LICENSE.md", "LICENSE.txt",
                      "CODE_OF_CONDUCT.md", "SECURITY.md", "NOTICE")),
    _Rule("docs.directory", FileSemanticType.docs,
          ClassificationConfidence.medium,
          path_starts_with=("docs/", "doc/", "documentation/")),
    _Rule("docs.markdown-other", FileSemanticType.docs,
          ClassificationConfidence.low, extension=(".md", ".rst", ".mdx")),

    # ----------------------------------------------------------- assets
    _Rule("asset.image", FileSemanticType.asset,
          ClassificationConfidence.high,
          extension=(".png", ".jpg", ".jpeg", ".gif", ".svg",
                     ".webp", ".ico", ".pdf")),
    _Rule("asset.font", FileSemanticType.asset,
          ClassificationConfidence.high,
          extension=(".woff", ".woff2", ".ttf", ".otf", ".eot")),
    _Rule("asset.audio-video", FileSemanticType.asset,
          ClassificationConfidence.high,
          extension=(".mp3", ".wav", ".mp4", ".mov", ".webm")),
)


class FileClassifier:
    """Classify a repo-relative path into a ``FileClassification``.

    The classifier is stateless and pure — same input, same output,
    every time. It's safe to share one instance across the scanner,
    repo operator, execution engine, etc.
    """

    def __init__(self, rules: tuple[_Rule, ...] = _RULES) -> None:
        self._rules = rules

    def classify(self, path: str) -> FileClassification:
        normalized = path.replace("\\", "/")
        lower_path = normalized.lower()
        name = normalized.rsplit("/", 1)[-1]
        lower_name = name.lower()

        triggered: list[str] = []
        primary_type: FileSemanticType | None = None
        primary_confidence: ClassificationConfidence | None = None

        for rule in self._rules:
            if rule.matches(normalized, name, lower_path, lower_name):
                triggered.append(rule.name)
                if primary_type is None:
                    primary_type = rule.semantic_type
                    primary_confidence = rule.confidence

        if primary_type is None:
            ext = ""
            if "." in lower_name:
                ext = "." + lower_name.rsplit(".", 1)[-1]
            if ext in _CODE_EXTENSIONS:
                primary_type = FileSemanticType.source
                triggered.append("default.source-by-extension")
            else:
                primary_type = FileSemanticType.unknown
                triggered.append("default.unknown")
            primary_confidence = ClassificationConfidence.low

        assert primary_type is not None and primary_confidence is not None
        return FileClassification(
            path=normalized,
            semantic_type=primary_type,
            confidence=primary_confidence,
            rules_triggered=tuple(triggered),
        )

    def classify_many(self, paths: list[str]) -> list[FileClassification]:
        return [self.classify(p) for p in paths]

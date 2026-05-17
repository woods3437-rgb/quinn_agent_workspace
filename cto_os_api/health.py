"""Phase 12 — `/system/health` aggregator.

Combines every operational signal we already collect into one structured
response. Status rollup:

- ``down``     SQLite unreachable.
- ``degraded`` any worker stale, any recent failed job, backup overdue,
               failed write events present.
- ``ok``       everything green.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .backups import BackupService, CADENCE_INTERVALS
from .heartbeat import STALE_AFTER_SECONDS, _ensure_aware, is_stale
from .intake import env_intake_enabled, intake_secret
from .models import (
    BackupCadence,
    GitHubWriteStatus,
    HealthStatus,
    JobStatus,
    SystemHealth,
    WorkerHeartbeat,
)
from .notifications import env_notifications_enabled
from .snapshots import APP_VERSION, SnapshotManager
from .sqlite_store import SQLiteStore


def _repo_root() -> Path:
    return Path(os.getenv("CTO_OS_REPO_ROOT", Path.cwd()))


class HealthService:
    def __init__(
        self,
        store: SQLiteStore,
        snapshots: SnapshotManager,
        backups: BackupService,
    ) -> None:
        self.store = store
        self.snapshots = snapshots
        self.backups = backups

    def build(self) -> SystemHealth:
        report = SystemHealth()
        report.api = {"reachable": True, "version": APP_VERSION}

        report.sqlite = self._sqlite()
        if not report.sqlite.get("reachable"):
            report.status = HealthStatus.down
            return report

        report.workers = self.store.list_worker_heartbeats()
        report.mempalace = self._mempalace()
        report.mcp = self._mcp()
        report.github = self._github()
        report.intake = self._intake()
        report.notifications = self._notifications()
        report.recent_failed_jobs = self._failed_jobs()
        report.recent_failed_write_events = self._failed_write_events()
        report.recent_blocked_suggestions = self._blocked_suggestions()
        report.backups = self._backups()

        report.status = self._rollup(report)
        return report

    # ----------------------------------------------------------- subsystems

    def _sqlite(self) -> dict:
        path = self.store.path
        info: dict[str, object] = {
            "path": str(path),
            "reachable": False,
            "journal_mode": "",
            "size_bytes": 0,
        }
        try:
            with self.store._connect() as conn:
                mode = conn.execute("PRAGMA journal_mode").fetchone()
                info["journal_mode"] = (mode[0] if mode else "").lower()
                info["reachable"] = True
        except Exception as exc:
            info["error"] = str(exc)
        if path.exists():
            info["size_bytes"] = path.stat().st_size
        return info

    def _mempalace(self) -> dict:
        # Best-effort: we don't want to spin up MemPalace just to ask. The
        # health endpoint reports the configured cache dir + whether the
        # palace directory exists.
        cache = os.getenv("CTO_OS_CHROMA_CACHE_DIR", "")
        palace = (
            os.getenv("CTO_OS_MEMPALACE_PATH")
            or os.getenv("MEMPALACE_PALACE_PATH")
            or ""
        )
        info = {
            "chroma_cache_dir": cache,
            "chroma_cache_exists": bool(cache) and Path(cache).exists(),
            "palace_path": palace,
            "palace_exists": bool(palace) and Path(palace).exists(),
        }
        return info

    def _mcp(self) -> dict:
        root = _repo_root()
        mcp_json = root / ".mcp.json"
        example = root / ".mcp.example.json"
        return {
            "config_detected": mcp_json.exists(),
            "config_path": str(mcp_json) if mcp_json.exists() else "",
            "example_present": example.exists(),
            "readonly_env": os.getenv("CTO_OS_MCP_READONLY", "0").strip() == "1",
        }

    def _github(self) -> dict:
        from .github_integration import GitHubIntegration

        return GitHubIntegration().status()

    def _intake(self) -> dict:
        return {
            "enabled": env_intake_enabled(),
            "secret_set": bool(intake_secret()),
        }

    def _notifications(self) -> dict:
        return {"enabled": env_notifications_enabled()}

    def _failed_jobs(self):
        out = []
        for project in self.store.list_projects():
            out.extend(
                job
                for job in self.store.list_jobs(project.id, status=JobStatus.failed.value)
            )
        return out[:10]

    def _failed_write_events(self):
        out = []
        for project in self.store.list_projects():
            out.extend(
                ev
                for ev in self.store.list_github_write_events(project.id)
                if ev.status in {GitHubWriteStatus.failed, GitHubWriteStatus.blocked}
            )
        return out[:10]

    def _blocked_suggestions(self):
        out = []
        for project in self.store.list_projects():
            out.extend(
                s
                for s in self.store.list_status_suggestions(
                    project.id, include_resolved=True
                )
                if s.dismissed and not s.applied
            )
        return out[:10]

    def _backups(self) -> dict:
        policy = self.backups.get_policy()
        snapshots = self.snapshots.list_snapshots()
        overdue = False
        if (
            policy.enabled
            and policy.cadence != BackupCadence.manual
            and CADENCE_INTERVALS.get(policy.cadence)
        ):
            if policy.last_run_at is None:
                overdue = True
            else:
                next_due = _ensure_aware(policy.last_run_at) + CADENCE_INTERVALS[policy.cadence]
                overdue = datetime.now(timezone.utc) > next_due
        return {
            "policy_enabled": policy.enabled,
            "cadence": policy.cadence.value,
            "max_snapshots": policy.max_snapshots,
            "snapshot_count": len(snapshots),
            "last_run_at": policy.last_run_at.isoformat() if policy.last_run_at else None,
            "overdue": overdue,
            "destination_path": policy.destination_path,
        }

    # ------------------------------------------------------------- rollup

    def _rollup(self, report: SystemHealth) -> HealthStatus:
        if any(is_stale(hb) for hb in report.workers):
            return HealthStatus.degraded
        if report.recent_failed_jobs:
            return HealthStatus.degraded
        if report.recent_failed_write_events:
            return HealthStatus.degraded
        if report.backups.get("overdue"):
            return HealthStatus.degraded
        return HealthStatus.ok

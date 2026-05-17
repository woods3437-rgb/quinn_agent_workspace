"use client";

import { useEffect, useState } from "react";
import { RetentionPolicy, RetentionRunResult, api } from "@/lib/api";

export default function RetentionSettingsPage() {
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [lastRun, setLastRun] = useState<RetentionRunResult | null>(null);

  async function load() {
    setPolicies(await api.retentionPolicies());
  }

  useEffect(() => {
    load();
  }, []);

  async function patch(policy: RetentionPolicy, update: Partial<RetentionPolicy>) {
    await api.updateRetentionPolicy(policy.target, update);
    await load();
  }

  async function run() {
    setLastRun(await api.runRetention());
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Settings</div>
        <h1>Retention</h1>
        <p>
          Each policy deletes rows older than its <code>days_to_keep</code>. <code>mcp_audit</code> requires
          both <code>enabled</code> AND <code>hard_delete_allowed</code> — a two-gate guard to keep the
          append-only audit append-only by default.
        </p>
        <button className="button" onClick={run}>
          Run retention now
        </button>
      </div>
      {lastRun && (
        <section className="panel">
          <h2>Last run</h2>
          <pre className="output">{JSON.stringify(lastRun, null, 2)}</pre>
        </section>
      )}
      <section className="stack">
        {policies.map((policy) => (
          <article className="card stack" key={policy.id}>
            <div className="spread">
              <h3>{policy.target}</h3>
              <span className="badge">{policy.enabled ? "enabled" : "disabled"}</span>
            </div>
            <div className="row">
              <label className="field">
                <span>Enabled</span>
                <input
                  type="checkbox"
                  checked={policy.enabled}
                  onChange={(e) => patch(policy, { enabled: e.target.checked })}
                />
              </label>
              <label className="field">
                <span>Days to keep</span>
                <input
                  type="number"
                  min={1}
                  max={3650}
                  value={policy.days_to_keep}
                  onChange={(e) => patch(policy, { days_to_keep: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>Hard delete allowed (mcp_audit gate)</span>
                <input
                  type="checkbox"
                  checked={policy.hard_delete_allowed}
                  onChange={(e) => patch(policy, { hard_delete_allowed: e.target.checked })}
                />
              </label>
            </div>
            <small>last run: {policy.last_run_at ?? "never"}</small>
          </article>
        ))}
      </section>
    </div>
  );
}

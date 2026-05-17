"use client";

import { useEffect, useState } from "react";
import {
  HealthAlertConditionType,
  HealthAlertEvaluation,
  HealthAlertRule,
  api
} from "@/lib/api";

const CONDITIONS: HealthAlertConditionType[] = [
  "degraded_samples",
  "failed_jobs",
  "backup_overdue",
  "worker_stale"
];

export default function HealthAlertsPage() {
  const [rules, setRules] = useState<HealthAlertRule[]>([]);
  const [lastEval, setLastEval] = useState<HealthAlertEvaluation[]>([]);
  const [name, setName] = useState("");
  const [condition, setCondition] = useState<HealthAlertConditionType>("degraded_samples");
  const [threshold, setThreshold] = useState(3);
  const [window, setWindow] = useState(60);

  async function load() {
    setRules(await api.healthAlertRules());
  }

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!name) return;
    await api.createHealthAlertRule({
      name,
      enabled: false,
      condition_type: condition,
      threshold,
      window_minutes: window,
      notification_rule_id: null
    });
    setName("");
    await load();
  }

  async function patch(rule: HealthAlertRule, update: Partial<HealthAlertRule>) {
    await api.updateHealthAlertRule(rule.id, update);
    await load();
  }

  async function evaluate() {
    setLastEval(await api.evaluateHealthAlertRules());
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Settings</div>
        <h1>Health Alert Rules</h1>
        <p>
          Evaluated after every health snapshot. On trigger, fires a notification via the Phase 9
          NotificationService with <code>event_type = health.alert.&lt;name&gt;</code> — your
          notification rule must match. Notifications still gated by <code>CTO_OS_ENABLE_NOTIFICATIONS</code>.
        </p>
      </div>
      <section className="panel stack">
        <h2>New rule</h2>
        <label className="field">
          <span>Name (used as event_type suffix)</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>Condition</span>
          <select value={condition} onChange={(e) => setCondition(e.target.value as HealthAlertConditionType)}>
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Threshold</span>
          <input type="number" min={1} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
        </label>
        <label className="field">
          <span>Window minutes</span>
          <input type="number" min={1} value={window} onChange={(e) => setWindow(Number(e.target.value))} />
        </label>
        <button className="button" onClick={create}>
          Create (starts disabled)
        </button>
      </section>
      <section className="panel">
        <button className="button secondary" onClick={evaluate}>
          Evaluate now
        </button>
        {lastEval.length > 0 && (
          <pre className="output">{JSON.stringify(lastEval, null, 2)}</pre>
        )}
      </section>
      <section className="stack">
        {rules.map((rule) => (
          <article className="card stack" key={rule.id}>
            <div className="spread">
              <h3>
                {rule.name} <small>· {rule.condition_type}</small>
              </h3>
              <span className="badge">{rule.enabled ? "enabled" : "disabled"}</span>
            </div>
            <div className="row">
              <label className="field">
                <span>Enabled</span>
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(e) => patch(rule, { enabled: e.target.checked })}
                />
              </label>
              <label className="field">
                <span>Threshold</span>
                <input
                  type="number"
                  min={1}
                  value={rule.threshold}
                  onChange={(e) => patch(rule, { threshold: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>Window minutes</span>
                <input
                  type="number"
                  min={1}
                  value={rule.window_minutes}
                  onChange={(e) => patch(rule, { window_minutes: Number(e.target.value) })}
                />
              </label>
            </div>
          </article>
        ))}
        {rules.length === 0 && <p>No alert rules.</p>}
      </section>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { NotificationChannel, NotificationEvent, NotificationRule, api } from "@/lib/api";

const CHANNELS: NotificationChannel[] = ["slack", "discord", "email", "webhook"];

export default function NotificationsSettingsPage() {
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [channel, setChannel] = useState<NotificationChannel>("webhook");
  const [eventType, setEventType] = useState("retrospective_generated");
  const [destination, setDestination] = useState("https://");
  const [busy, setBusy] = useState(false);

  async function load() {
    setRules(await api.notificationRules());
    setEvents(await api.notificationEvents());
  }

  useEffect(() => {
    load();
  }, []);

  async function create() {
    setBusy(true);
    try {
      await api.createNotificationRule({
        channel,
        event_type: eventType,
        destination,
        enabled: false,
        project_id: null,
        secret_ref: null
      });
      setDestination("https://");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function toggle(rule: NotificationRule) {
    await api.updateNotificationRule(rule.id, { enabled: !rule.enabled });
    await load();
  }

  async function test(rule: NotificationRule) {
    await api.testNotification(rule.id, { test: true });
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Settings</div>
        <h1>Notifications</h1>
        <p>
          Notifications are off by default. Set <code>CTO_OS_ENABLE_NOTIFICATIONS=1</code> AND enable a rule for it
          to send.
        </p>
      </div>
      <section className="panel stack">
        <h2>New rule</h2>
        <label className="field">
          <span>Channel</span>
          <select value={channel} onChange={(e) => setChannel(e.target.value as NotificationChannel)}>
            {CHANNELS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Event type</span>
          <input value={eventType} onChange={(e) => setEventType(e.target.value)} />
        </label>
        <label className="field">
          <span>Destination (HTTPS URL or email)</span>
          <input value={destination} onChange={(e) => setDestination(e.target.value)} />
        </label>
        <button className="button" onClick={create} disabled={busy}>
          Create rule (starts disabled)
        </button>
      </section>
      <section className="stack">
        <h2>Rules</h2>
        {rules.map((rule) => (
          <article className="card stack" key={rule.id}>
            <div className="spread">
              <h3>
                {rule.channel} · {rule.event_type}
              </h3>
              <span className="badge">{rule.enabled ? "enabled" : "disabled"}</span>
            </div>
            <p>{rule.destination}</p>
            <div className="row">
              <button className="button secondary" onClick={() => toggle(rule)}>
                {rule.enabled ? "Disable" : "Enable"}
              </button>
              <button className="button secondary" onClick={() => test(rule)}>
                Send test
              </button>
            </div>
          </article>
        ))}
        {rules.length === 0 && <p>No rules yet.</p>}
      </section>
      <section className="stack">
        <h2>Recent events</h2>
        {events.slice(0, 20).map((event) => (
          <article className="card" key={event.id}>
            <strong>{event.event_type}</strong> — {event.status} {event.error_message && `· ${event.error_message}`}
          </article>
        ))}
      </section>
    </div>
  );
}

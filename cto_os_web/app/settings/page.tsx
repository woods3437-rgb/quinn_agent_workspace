import { API_BASE } from "@/lib/api";
import Link from "next/link";

export default function SettingsPage() {
  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Private Internal Settings</div>
        <h1>Settings</h1>
        <p>Phase 1 is local-first and intentionally avoids public SaaS features.</p>
      </div>
      <section className="panel stack">
        <h2>Runtime</h2>
        <p>API base: {API_BASE}</p>
        <p>No billing, public signup, tenant marketplace, or complex permission model is enabled.</p>
      </section>
      <section className="panel stack">
        <h2>Memory Policy</h2>
        <p>Project-scoped retrieval is the default. Cross-project search must be explicitly enabled in the workspace request.</p>
      </section>
      <section className="panel stack">
        <h2>Snapshots</h2>
        <p>Create or restore local SQLite snapshots before risky operations.</p>
        <Link className="button secondary" href="/settings/snapshots">Open snapshots</Link>
      </section>
    </div>
  );
}

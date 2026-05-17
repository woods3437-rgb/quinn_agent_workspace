"use client";

import { FormEvent, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, Decision } from "@/lib/api";

export default function DecisionsPage({ params }: { params: { id: string } }) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [typeFilter, setTypeFilter] = useState("all");
  const [impactFilter, setImpactFilter] = useState("all");
  const [form, setForm] = useState({
    title: "",
    context: "",
    decision: "",
    decision_type: "technical",
    rationale: "",
    tradeoffs: "",
    alternatives_considered: "",
    impact_level: "medium",
    consequences: "",
    tags: ""
  });

  async function load() {
    setDecisions(await api.decisions(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  async function createDecision(event: FormEvent) {
    event.preventDefault();
    await api.createDecision(params.id, {
      title: form.title,
      context: form.context,
      decision: form.decision,
      decision_type: form.decision_type,
      rationale: form.rationale,
      tradeoffs: form.tradeoffs,
      alternatives_considered: form.alternatives_considered.split("\n").map((item) => item.trim()).filter(Boolean),
      impact_level: form.impact_level,
      consequences: form.consequences,
      tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      linked_task_ids: [],
      linked_output_ids: [],
      supersedes_decision_id: null
    });
    setForm({ title: "", context: "", decision: "", decision_type: "technical", rationale: "", tradeoffs: "", alternatives_considered: "", impact_level: "medium", consequences: "", tags: "" });
    await load();
  }

  const visible = decisions.filter((item) => {
    if (typeFilter !== "all" && item.decision_type !== typeFilter) return false;
    if (impactFilter !== "all" && item.impact_level !== impactFilter) return false;
    return true;
  });

  return (
    <div className="stack">
      <div><div className="eyebrow">Decision Log</div><h1>Decisions</h1><p>Every decision is timestamped and tied to this project.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={createDecision}>
        <h2>Log Decision</h2>
        <div className="grid">
          <label className="field"><span>decision_type</span><select value={form.decision_type} onChange={(e) => setForm({ ...form, decision_type: e.target.value })}>{["product", "technical", "design", "business", "growth", "financial", "operational"].map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="field"><span>impact_level</span><select value={form.impact_level} onChange={(e) => setForm({ ...form, impact_level: e.target.value })}>{["low", "medium", "high"].map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        {(["title", "context", "decision", "rationale", "tradeoffs", "alternatives_considered", "consequences", "tags"] as const).map((key) => (
          <label className="field" key={key}>
            <span>{key}</span>
            {key === "title" || key === "tags" ? (
              <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            ) : (
              <textarea value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            )}
          </label>
        ))}
        <button className="button row" type="submit"><Plus size={17} /> Save decision</button>
      </form>
      <div className="panel row">
        <label className="field"><span>Type</span><select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>{["all", "product", "technical", "design", "business", "growth", "financial", "operational"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="field"><span>Impact</span><select value={impactFilter} onChange={(e) => setImpactFilter(e.target.value)}>{["all", "low", "medium", "high"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <span className="badge">source-of-truth relevance: linked outputs/tasks visible per decision</span>
      </div>
      <section className="stack">
        {visible.map((item) => (
          <article className="card stack" key={item.id}>
            <div className="spread"><h2>{item.title}</h2><span className="muted">{new Date(item.created_at).toLocaleString()}</span></div>
            <div className="row"><span className="badge">{item.decision_type}</span><span className="badge">{item.impact_level}</span></div>
            <p><strong>Decision:</strong> {item.decision}</p>
            {item.rationale && <p><strong>Rationale:</strong> {item.rationale}</p>}
            {item.tradeoffs && <p><strong>Tradeoffs:</strong> {item.tradeoffs}</p>}
            {item.alternatives_considered.length > 0 && <p><strong>Alternatives:</strong> {item.alternatives_considered.join(", ")}</p>}
            {(item.linked_task_ids.length > 0 || item.linked_output_ids.length > 0) && <p><strong>Links:</strong> {item.linked_task_ids.length} tasks, {item.linked_output_ids.length} outputs</p>}
          </article>
        ))}
      </section>
    </div>
  );
}

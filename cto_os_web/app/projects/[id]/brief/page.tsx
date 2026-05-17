"use client";

import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, GeneratedOutput, ProjectBrief } from "@/lib/api";

export default function BriefPage({ params }: { params: { id: string } }) {
  const [brief, setBrief] = useState<ProjectBrief | null>(null);
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [pin, setPin] = useState(false);

  useEffect(() => {
    api.brief(params.id).then(setBrief);
  }, []);

  async function generate() {
    const result = await api.generateBrief(params.id, { save_output: true, pin_to_memory: pin });
    setOutput(result);
    setBrief(await api.brief(params.id));
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Source of Truth</div><h1>Project Brief</h1><p>Current truth assembled from pinned memory, decisions, architecture, roadmap, and active tasks.</p></div>
      <ProjectTabs projectId={params.id} />
      <div className="row"><label className="row"><input style={{ width: 18 }} type="checkbox" checked={pin} onChange={(e) => setPin(e.target.checked)} /> Pin generated brief</label><button className="button row" onClick={generate}><FileText size={17} /> Generate brief</button></div>
      {brief && (
        <section className="grid">
          <BriefCard title="Project summary" value={brief.project_summary} />
          <BriefCard title="Current goal" value={brief.current_goal} />
          <BriefCard title="Audience/customer" value={brief.audience_customer} />
          <BriefCard title="Product thesis" value={brief.product_thesis} />
          <BriefCard title="Monetization thesis" value={brief.monetization_thesis} />
          <BriefCard title="Current tech stack" value={brief.current_tech_stack} />
          <BriefList title="Active roadmap" items={brief.active_roadmap} />
          <BriefList title="Key decisions" items={brief.key_decisions} />
          <BriefList title="Open risks" items={brief.open_risks} />
          <BriefList title="Next best actions" items={brief.next_best_actions} />
        </section>
      )}
      {output && <section className="panel stack"><h2>Generated Brief</h2><div className="output">{output.output}</div></section>}
    </div>
  );
}

function BriefCard({ title, value }: { title: string; value: string }) {
  return <article className="card"><h2>{title}</h2><p>{value}</p></article>;
}

function BriefList({ title, items }: { title: string; items: string[] }) {
  return <article className="card"><h2>{title}</h2><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></article>;
}

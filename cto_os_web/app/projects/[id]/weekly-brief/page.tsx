"use client";

import { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { GeneratedOutput, api } from "@/lib/api";

export default function WeeklyBriefPage({ params }: { params: { id: string } }) {
  const [briefs, setBriefs] = useState<GeneratedOutput[]>([]);
  const [latest, setLatest] = useState<GeneratedOutput | null>(null);

  async function load() {
    const items = await api.briefs(params.id);
    setBriefs(items.filter((item) => item.metadata?.output_type === "weekly_brief"));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    const output = await api.generateWeeklyBrief(params.id);
    setLatest(output);
    await load();
  }

  return (
    <div className="stack">
      <div className="spread">
        <div><div className="eyebrow">Weekly CTO Brief</div><h1>Weekly Brief</h1><p>What changed, decisions, completed work, blocked work, open risks, and next focus.</p></div>
        <button className="button row" onClick={generate}><CalendarClock size={17} /> Generate weekly brief</button>
      </div>
      <ProjectTabs projectId={params.id} />
      {latest && <section className="panel stack"><h2>Latest Weekly Brief</h2><div className="output">{latest.output}</div></section>}
      <section className="stack">
        {briefs.map((brief) => <article className="card stack" key={brief.id}><div className="spread"><h2>Weekly CTO Brief</h2><span className="muted">{new Date(brief.created_at).toLocaleString()}</span></div><div className="output">{brief.output}</div></article>)}
      </section>
    </div>
  );
}

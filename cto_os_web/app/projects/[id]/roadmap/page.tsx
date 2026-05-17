"use client";

import { FormEvent, useEffect, useState } from "react";
import { ListChecks, Route } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, GeneratedOutput } from "@/lib/api";

export default function RoadmapPage({ params }: { params: { id: string } }) {
  const [prompt, setPrompt] = useState("");
  const [pin, setPin] = useState(false);
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    const items = await api.outputs(params.id);
    setOutputs(items.filter((item) => item.metadata?.output_type === "roadmap"));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    const result = await api.generateRoadmap(params.id, { prompt, save_output: true, pin_to_memory: pin });
    setOutput(result);
    await load();
  }

  async function makeTasks(outputId?: string) {
    const tasks = await api.generateTasksFromRoadmap(params.id, { output_id: outputId ?? null, limit: 8 });
    setMessage(`Created ${tasks.length} tasks from roadmap.`);
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Roadmap Builder</div><h1>Roadmap</h1><p>Break the project into phases, milestones, dependencies, risks, acceptance criteria, and build order.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={generate}>
        <label className="field"><span>Roadmap focus</span><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="What outcome should this roadmap optimize for?" /></label>
        <label className="row"><input style={{ width: 18 }} type="checkbox" checked={pin} onChange={(e) => setPin(e.target.checked)} /> Pin roadmap as source of truth</label>
        <button className="button row" type="submit"><Route size={17} /> Generate roadmap</button>
      </form>
      {message && <div className="panel">{message}</div>}
      {output && <section className="panel stack"><div className="spread"><h2>Latest Roadmap</h2><button className="button secondary row" onClick={() => makeTasks(output.id)}><ListChecks size={17} /> Convert to tasks</button></div><div className="output">{output.output}</div></section>}
      <section className="stack">
        {outputs.map((item) => <article className="card stack" key={item.id}><div className="spread"><h2>Roadmap Output</h2><button className="button secondary row" onClick={() => makeTasks(item.id)}><ListChecks size={17} /> Tasks</button></div><div className="output">{item.output}</div></article>)}
      </section>
    </div>
  );
}

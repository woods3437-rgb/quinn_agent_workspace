"use client";

import { FormEvent, useEffect, useState } from "react";
import { Cpu, FileCode2 } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, GeneratedOutput } from "@/lib/api";

export default function ArchitecturePage({ params }: { params: { id: string } }) {
  const [prompt, setPrompt] = useState("");
  const [pin, setPin] = useState(false);
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);

  async function load() {
    const items = await api.outputs(params.id);
    setOutputs(items.filter((item) => item.metadata?.output_type === "architecture"));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    const result = await api.generateArchitecture(params.id, { prompt, save_output: true, pin_to_memory: pin });
    setOutput(result);
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Architecture Generator</div><h1>Architecture</h1><p>Generate stack, API, database, infrastructure, cost, security, and complexity guidance from project memory.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={generate}>
        <label className="field"><span>Architecture focus</span><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="What tradeoff or system area should the CTO review?" /></label>
        <label className="row"><input style={{ width: 18 }} type="checkbox" checked={pin} onChange={(e) => setPin(e.target.checked)} /> Pin generated architecture as source of truth</label>
        <button className="button row" type="submit"><Cpu size={17} /> Generate architecture</button>
      </form>
      {output && <section className="panel stack"><h2>Latest Architecture</h2><div className="output">{output.output}</div></section>}
      <section className="stack">
        {outputs.map((item) => <article className="card stack" key={item.id}><div className="spread"><h2><FileCode2 size={18} /> Architecture Output</h2><span className="muted">{new Date(item.created_at).toLocaleString()}</span></div><div className="output">{item.output}</div></article>)}
      </section>
    </div>
  );
}

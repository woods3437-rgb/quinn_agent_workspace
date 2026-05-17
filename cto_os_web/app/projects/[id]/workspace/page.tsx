"use client";

import { FormEvent, useEffect, useState } from "react";
import { Brain, Save } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { Agent, GeneratedOutput, api } from "@/lib/api";

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [memoryQuery, setMemoryQuery] = useState("");
  const [crossProject, setCrossProject] = useState(false);
  const [saveAsMemory, setSaveAsMemory] = useState(false);
  const [output, setOutput] = useState<GeneratedOutput | null>(null);

  useEffect(() => {
    api.agents().then((items) => {
      setAgents(items);
      setAgentId(items[0]?.id ?? "");
    });
  }, []);

  async function generate(event: FormEvent) {
    event.preventDefault();
    const result = await api.generate(params.id, {
      agent_id: agentId,
      prompt,
      memory_query: memoryQuery,
      cross_project: crossProject,
      save_output: true,
      save_as_memory: saveAsMemory
    });
    setOutput(result);
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">AI Workspace</div><h1>Workspace</h1><p>Select an agent, retrieve scoped memory, and save generated work back to the project.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={generate}>
        <label className="field">
          <span>Agent Selector</span>
          <select value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            {agents.map((agent) => <option value={agent.id} key={agent.id}>{agent.name}</option>)}
          </select>
        </label>
        <label className="field"><span>Prompt</span><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} /></label>
        <label className="field"><span>Memory query</span><input value={memoryQuery} onChange={(e) => setMemoryQuery(e.target.value)} placeholder="Defaults to the prompt when blank" /></label>
        <div className="row">
          <label className="row"><input style={{ width: 18 }} type="checkbox" checked={crossProject} onChange={(e) => setCrossProject(e.target.checked)} /> Cross-project search</label>
          <label className="row"><input style={{ width: 18 }} type="checkbox" checked={saveAsMemory} onChange={(e) => setSaveAsMemory(e.target.checked)} /> Save output as memory</label>
        </div>
        <button className="button row" type="submit"><Brain size={17} /> Generate</button>
      </form>
      {output && (
        <section className="panel stack">
          <div className="spread"><h2>Generated Output</h2><span className="badge"><Save size={14} /> Saved</span></div>
          <div className="output">{output.output}</div>
        </section>
      )}
    </div>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import { Copy, Plus, Wand2 } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, GeneratedOutput, PromptTemplate } from "@/lib/api";

export default function PromptsPage({ params }: { params: { id: string } }) {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selected, setSelected] = useState<PromptTemplate | null>(null);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [form, setForm] = useState({ name: "", description: "", category: "engineering", agent_type: "engineering-builder", template_body: "" });

  async function load() {
    const items = await api.promptTemplates(params.id);
    setTemplates(items);
    setSelected((current) => current ?? items[0] ?? null);
  }

  useEffect(() => {
    load();
  }, []);

  async function createTemplate(event: FormEvent) {
    event.preventDefault();
    await api.createPromptTemplate({ ...form, project_id: params.id, template: form.template_body, input_variables: [] });
    setForm({ name: "", description: "", category: "engineering", agent_type: "engineering-builder", template_body: "" });
    await load();
  }

  async function generate() {
    if (!selected) return;
    const result = await api.generatePromptFromTemplate(params.id, { template_id: selected.id, variables, save_output: true, agent_id: selected.agent_type });
    setOutput(result);
  }

  async function duplicate(template: PromptTemplate) {
    await api.duplicatePromptTemplate(template.id, params.id);
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Prompt Library</div><h1>Prompts</h1><p>Reusable global and project-specific prompts for build, research, strategy, debugging, and handoff work.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="grid">
        <div className="panel stack">
          <h2>Templates</h2>
          {templates.map((template) => <button className="task-card" key={template.id} onClick={() => setSelected(template)}><strong>{template.name}</strong><small>{template.category} {template.project_id ? "project" : "global"}</small></button>)}
        </div>
        <div className="panel stack">
          <h2>{selected?.name ?? "Select a template"}</h2>
          <p>{selected?.description}</p>
          {(selected?.input_variables ?? []).map((name) => <label className="field" key={name}><span>{name}</span><input value={variables[name] ?? ""} onChange={(e) => setVariables({ ...variables, [name]: e.target.value })} /></label>)}
          <div className="output">{selected?.template_body || selected?.template}</div>
          <div className="row"><button className="button row" onClick={generate}><Wand2 size={17} /> Generate prompt</button>{selected && <button className="button secondary row" onClick={() => duplicate(selected)}><Copy size={17} /> Duplicate</button>}</div>
        </div>
      </section>
      <form className="panel stack" onSubmit={createTemplate}>
        <h2>Project Template</h2>
        <label className="field"><span>Name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="field"><span>Description</span><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <label className="field"><span>Template body</span><textarea value={form.template_body} onChange={(e) => setForm({ ...form, template_body: e.target.value })} placeholder="Use {{project}}, {{task}}, {{target}}, or your own variables." /></label>
        <button className="button row" type="submit"><Plus size={17} /> Save template</button>
      </form>
      {output && <section className="panel stack"><h2>Generated Prompt</h2><div className="output">{output.output}</div></section>}
    </div>
  );
}

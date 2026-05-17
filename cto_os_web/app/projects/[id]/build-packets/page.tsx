"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { BuildPacket, Task, api } from "@/lib/api";

export default function BuildPacketsPage({ params }: { params: { id: string } }) {
  const [packets, setPackets] = useState<BuildPacket[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [title, setTitle] = useState("");
  const [selectedPrompt, setSelectedPrompt] = useState("");

  async function load() {
    const [packetItems, taskItems] = await Promise.all([api.buildPackets(params.id), api.tasks(params.id)]);
    setPackets(packetItems);
    setTasks(taskItems);
    if (!taskId && taskItems[0]) setTaskId(taskItems[0].id);
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    await api.generateBuildPacket(params.id, { task_id: taskId || undefined, source_text: sourceText, title, save_to_memory: false });
    setSourceText("");
    await load();
  }

  async function createTask(packet: BuildPacket) {
    await api.createTask(params.id, {
      title: `Follow up: ${packet.title}`,
      description: packet.summary,
      status: "backlog",
      priority: "medium",
      category: "backend",
      acceptance_criteria: packet.acceptance_criteria,
      dependencies: [],
      linked_memory_ids: packet.relevant_memories,
      linked_decision_ids: packet.relevant_decisions,
      linked_output_ids: []
    });
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Build Handoff</div><h1>Build Packets</h1><p>Codex, Claude, Cursor, and developer-ready packets grounded in project memory.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field"><span>Task</span><select value={taskId} onChange={(event) => setTaskId(event.target.value)}><option value="">Manual packet</option>{tasks.map((task) => <option value={task.id} key={task.id}>{task.title}</option>)}</select></label>
          <label className="field"><span>Title override</span><input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        </div>
        <label className="field"><span>Manual context</span><textarea value={sourceText} onChange={(event) => setSourceText(event.target.value)} /></label>
        <button className="button" onClick={generate}>Generate build packet</button>
      </section>
      {selectedPrompt && <section className="panel stack"><h2>Prompt</h2><div className="output">{selectedPrompt}</div></section>}
      <section className="stack">
        {packets.map((packet) => (
          <article className="card stack" key={packet.id}>
            <div className="spread"><h2>{packet.title}</h2><span className="muted">{new Date(packet.created_at).toLocaleString()}</span></div>
            <p>{packet.summary}</p>
            <div className="row">
              <button className="button secondary" onClick={() => setSelectedPrompt(packet.codex_prompt)}>Copy Codex prompt</button>
              <button className="button secondary" onClick={() => setSelectedPrompt(packet.claude_prompt)}>Copy Claude prompt</button>
              <button className="button secondary" onClick={() => setSelectedPrompt(packet.cursor_prompt)}>Copy Cursor prompt</button>
              <button className="button secondary" onClick={() => createTask(packet)}>Create follow-up task</button>
            </div>
            <div className="output">{packet.implementation_steps.map((step) => `- ${step}`).join("\n")}</div>
          </article>
        ))}
      </section>
    </div>
  );
}

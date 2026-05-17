"use client";

import { FormEvent, useEffect, useState } from "react";
import { Pin, Plus } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, Memory, Project } from "@/lib/api";

export default function MemoryPage({ params }: { params: { id: string } }) {
  const [project, setProject] = useState<Project | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [pinned, setPinned] = useState(false);

  async function load() {
    const [projectData, memoryData] = await Promise.all([api.project(params.id), api.memories(params.id)]);
    setProject(projectData);
    setMemories(memoryData);
  }

  useEffect(() => {
    load();
  }, []);

  async function createMemory(event: FormEvent) {
    event.preventDefault();
    await api.createMemory(params.id, {
      title,
      content,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      pinned
    });
    setTitle("");
    setContent("");
    setTags("");
    setPinned(false);
    await load();
  }

  async function togglePin(memory: Memory) {
    await api.pinMemory(params.id, memory.id, !memory.pinned);
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Memory Space</div>
        <h1>{project?.name ?? "Project"}</h1>
        <p>Only this project&apos;s memory is retrieved by default.</p>
      </div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={createMemory}>
        <h2>Add Memory</h2>
        <label className="field"><span>Title</span><input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label className="field"><span>Content</span><textarea value={content} onChange={(e) => setContent(e.target.value)} /></label>
        <label className="field"><span>Tags</span><input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="strategy, customer, architecture" /></label>
        <label className="row"><input style={{ width: 18 }} type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} /> Pin as source of truth</label>
        <button className="button row" type="submit"><Plus size={17} /> Save memory</button>
      </form>
      <section className="grid">
        {memories.map((memory) => (
          <article className="card stack" key={memory.id}>
            <div className="spread">
              <h2>{memory.title}</h2>
              <button className="button secondary row" onClick={() => togglePin(memory)} title="Toggle source-of-truth pin">
                <Pin size={16} /> {memory.pinned ? "Pinned" : "Pin"}
              </button>
            </div>
            <p>{memory.content}</p>
            <div className="row">{memory.tags.map((tag) => <span className="badge" key={tag}>{tag}</span>)}</div>
          </article>
        ))}
      </section>
    </div>
  );
}

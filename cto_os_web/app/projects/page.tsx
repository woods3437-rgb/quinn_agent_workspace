"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { api, Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setProjects(await api.projects());
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
  }, []);

  async function createProject(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    await api.createProject({ name, description });
    setName("");
    setDescription("");
    await load();
  }

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <div className="eyebrow">Private CTO OS</div>
          <h1>Projects</h1>
          <p>Project-specific memory spaces for strategy, decisions, execution, and generated work.</p>
        </div>
      </div>

      {error && <div className="panel">{error}</div>}

      <form className="panel stack" onSubmit={createProject}>
        <h2>New Project</h2>
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Internal platform rebuild" />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What this project is trying to become." />
        </label>
        <button className="button row" type="submit">
          <Plus size={17} /> Create project
        </button>
      </form>

      <section className="grid">
        {projects.map((project) => (
          <Link className="card stack" href={`/projects/${project.id}`} key={project.id}>
            <div className="spread">
              <h2>{project.name}</h2>
              <span className="badge">{project.status}</span>
            </div>
            <p>{project.description || "No description yet."}</p>
            <span className="muted">Updated {new Date(project.updated_at).toLocaleString()}</span>
          </Link>
        ))}
      </section>
    </div>
  );
}

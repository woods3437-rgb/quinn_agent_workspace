"use client";

import { FormEvent, useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { GitStatus, RepoFile, RepoScan, Repository, api } from "@/lib/api";

export default function RepositoriesPage({ params }: { params: { id: string } }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState<Repository["provider"]>("manual");
  const [localPath, setLocalPath] = useState("");
  const [exportText, setExportText] = useState("");
  const [importText, setImportText] = useState("");
  const [scans, setScans] = useState<Record<string, RepoScan[]>>({});
  const [files, setFiles] = useState<Record<string, RepoFile[]>>({});
  const [git, setGit] = useState<Record<string, GitStatus>>({});
  const [github, setGithub] = useState<Record<string, string>>({});

  async function load() {
    setRepositories(await api.repositories(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    await api.createRepository(params.id, { provider, name, url, default_branch: "main", local_path: localPath || null, notes: "" });
    setName("");
    setUrl("");
    setLocalPath("");
    await load();
  }

  async function exportProject() {
    setExportText(JSON.stringify(await api.exportProject(params.id), null, 2));
  }

  async function importProject() {
    if (!importText.trim()) return;
    await api.importProject(JSON.parse(importText));
    setImportText("");
  }

  async function scan(repo: Repository) {
    await api.scanRepository(params.id, repo.id);
    setScans({ ...scans, [repo.id]: await api.repoScans(params.id, repo.id) });
    setFiles({ ...files, [repo.id]: await api.repoFiles(params.id, repo.id) });
  }

  async function indexToMemory(repo: Repository) {
    await api.indexRepoToMemory(params.id, repo.id);
  }

  async function loadGit(repo: Repository) {
    setGit({ ...git, [repo.id]: await api.gitStatus(params.id, repo.id) });
  }

  async function syncGithub(repo: Repository) {
    const result = await api.githubSync(params.id, repo.id);
    setGithub({ ...github, [repo.id]: `${result.issues} issues, ${result.pull_requests} PRs synced` });
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Repo Context</div><h1>Repositories</h1><p>Local/manual repository records and future GitHub boundaries.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={create}>
        <div className="grid">
          <label className="field"><span>Name</span><input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <label className="field"><span>Provider</span><select value={provider} onChange={(event) => setProvider(event.target.value as Repository["provider"])}><option>manual</option><option>local</option><option>github</option></select></label>
          <label className="field"><span>URL</span><input value={url} onChange={(event) => setUrl(event.target.value)} /></label>
          <label className="field"><span>Local path</span><input value={localPath} onChange={(event) => setLocalPath(event.target.value)} /></label>
        </div>
        <button className="button">Add repository</button>
      </form>
      <section className="grid">
        {repositories.map((repo) => (
          <article className="card stack" key={repo.id}>
            <div className="spread"><h2>{repo.name}</h2><span className="badge">{repo.provider}</span></div>
            <p>{repo.url || repo.local_path || "Manual context only."}</p>
            <div className="row"><button className="button secondary" onClick={() => scan(repo)}>Scan</button><button className="button secondary" onClick={() => indexToMemory(repo)}>Index to memory</button><button className="button secondary" onClick={() => loadGit(repo)}>Git status</button><button className="button secondary" onClick={() => syncGithub(repo)}>GitHub sync</button></div>
            {scans[repo.id]?.[0] && <div className="output">{scans[repo.id][0].summary + "\n\nStack: " + scans[repo.id][0].tech_stack.join(", ") + "\nTests: " + scans[repo.id][0].test_commands.join(", ")}</div>}
            {git[repo.id] && <div className="output">{`Branch: ${git[repo.id].current_branch || "unknown"}\n${git[repo.id].status_summary}\n\nChanged:\n${git[repo.id].changed_files.join("\n")}`}</div>}
            {github[repo.id] && <p>{github[repo.id]}</p>}
            {files[repo.id] && <div className="output">{files[repo.id].slice(0, 20).map((file) => `${file.role} ${file.path}`).join("\n")}</div>}
          </article>
        ))}
      </section>
      <section className="panel stack">
        <h2>Project Import / Export</h2>
        <div className="row"><button className="button secondary" onClick={exportProject}>Export project JSON</button><button className="button secondary" onClick={importProject}>Import pasted JSON</button></div>
        <textarea value={exportText || importText} onChange={(event) => { setImportText(event.target.value); setExportText(""); }} placeholder="Export appears here. Paste a project export here to import." />
      </section>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { ApprovedCommand, Repository, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function CommandsPage({ params }: { params: { id: string } }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [commands, setCommands] = useState<ApprovedCommand[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [command, setCommand] = useState("npm test");
  const [commandType, setCommandType] = useState<ApprovedCommand["command_type"]>("test");
  const [output, setOutput] = useState("");

  async function load(repoId = repositoryId) {
    const repos = await api.repositories(params.id);
    setRepositories(repos);
    const active = repoId || repos[0]?.id || "";
    setRepositoryId(active);
    if (active) setCommands(await api.commands(params.id, active));
  }
  useEffect(() => { load(); }, []);

  async function approve() {
    if (!repositoryId) return;
    await api.approveCommand(params.id, repositoryId, { command, command_type: commandType, working_directory: "." });
    await load(repositoryId);
  }

  async function run(item: ApprovedCommand) {
    const result = await api.runCommand(params.id, item.repository_id, item.id);
    setOutput(`${result.status}\n\n${result.output}`);
    await load(item.repository_id);
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Controlled Execution</div><h1>Commands</h1><p>Approved test/lint/typecheck/build commands only. No arbitrary shell.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field"><span>Repository</span><select value={repositoryId} onChange={(e) => load(e.target.value)}>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select></label>
          <label className="field"><span>Type</span><select value={commandType} onChange={(e) => setCommandType(e.target.value as ApprovedCommand["command_type"])}>{["test", "lint", "typecheck", "build"].map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        <label className="field"><span>Command</span><input value={command} onChange={(e) => setCommand(e.target.value)} /></label>
        <button className="button" onClick={approve}>Approve command</button>
      </section>
      {output && <section className="panel output">{output}</section>}
      <section className="stack">{commands.map((item) => <article className="card stack" key={item.id}><div className="spread"><h2>{item.command}</h2><span className="badge">{item.command_type}</span></div><button className="button secondary" onClick={() => run(item)}>Run</button></article>)}</section>
    </div>
  );
}

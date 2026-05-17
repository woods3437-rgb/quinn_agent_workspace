"use client";

import { useEffect, useState } from "react";
import { BranchPlan, BuildPacket, GitHubWriteEvent, Repository, Task, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function BranchPlansPage({ params }: { params: { id: string } }) {
  const [plans, setPlans] = useState<BranchPlan[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [packets, setPackets] = useState<BuildPacket[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [packetId, setPacketId] = useState("");
  const [objective, setObjective] = useState("");
  const [previews, setPreviews] = useState<Record<string, GitHubWriteEvent>>({});
  const [results, setResults] = useState<Record<string, GitHubWriteEvent>>({});

  async function load() {
    const [repos, taskItems, packetItems, planItems] = await Promise.all([
      api.repositories(params.id),
      api.tasks(params.id),
      api.buildPackets(params.id),
      api.branchPlans(params.id)
    ]);
    setRepositories(repos);
    setTasks(taskItems);
    setPackets(packetItems);
    setPlans(planItems);
    if (!repositoryId && repos[0]) setRepositoryId(repos[0].id);
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!repositoryId) return;
    await api.generateBranchPlan(params.id, {
      repository_id: repositoryId,
      task_id: taskId || undefined,
      build_packet_id: packetId || undefined,
      objective
    });
    await load();
  }

  async function previewBranch(plan: BranchPlan) {
    setPreviews({ ...previews, [plan.id]: await api.githubPreviewBranch(params.id, plan.id) });
  }

  async function createBranch(plan: BranchPlan) {
    try {
      const event = await api.githubCreateBranch(params.id, plan.id, { approved: true, dry_run: false });
      setResults({ ...results, [plan.id]: event });
      await load();
    } catch (err) {
      setResults({
        ...results,
        [plan.id]: {
          id: "local",
          project_id: params.id,
          entity_type: "branch_plan",
          entity_id: plan.id,
          action: "create_branch",
          dry_run: false,
          approved: true,
          payload_json: {},
          response_json: {},
          status: "failed",
          error_message: String((err as Error).message ?? err),
          created_at: new Date().toISOString()
        }
      });
    }
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Repo-Aware Operator</div>
        <h1>Branch Plans</h1>
        <p>Generate plans locally. Branch creation on GitHub requires explicit confirmation.</p>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field">
            <span>Repository</span>
            <select value={repositoryId} onChange={(e) => setRepositoryId(e.target.value)}>
              {repositories.map((repo) => (
                <option value={repo.id} key={repo.id}>
                  {repo.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Task</span>
            <select value={taskId} onChange={(e) => setTaskId(e.target.value)}>
              <option value="">None</option>
              {tasks.map((task) => (
                <option value={task.id} key={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Build packet</span>
            <select value={packetId} onChange={(e) => setPacketId(e.target.value)}>
              <option value="">None</option>
              {packets.map((packet) => (
                <option value={packet.id} key={packet.id}>
                  {packet.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          <span>Objective</span>
          <input value={objective} onChange={(e) => setObjective(e.target.value)} />
        </label>
        <button className="button" onClick={generate}>
          Generate branch plan
        </button>
      </section>
      <section className="stack">
        {plans.map((plan) => (
          <article className="card stack" key={plan.id}>
            <div className="spread">
              <h2>{plan.branch_name}</h2>
              <span className="badge">{plan.files_to_change.length} files</span>
            </div>
            <p>{plan.objective}</p>
            <div className="output">
              {[
                "Files to inspect:",
                ...plan.files_to_inspect.map((f) => `- ${f}`),
                "",
                "Steps:",
                ...plan.implementation_steps.map((s) => `- ${s}`),
                "",
                "Tests:",
                ...plan.test_commands.map((c) => `- ${c}`)
              ].join("\n")}
            </div>
            {plan.github_branch_url && (
              <p>
                Branch: <a href={plan.github_branch_url}>{plan.github_branch_name}</a> ({plan.github_sync_status})
              </p>
            )}
            <div className="row">
              <button className="button secondary" onClick={() => previewBranch(plan)}>
                Preview GitHub branch
              </button>
              {previews[plan.id] && (
                <button className="button" onClick={() => createBranch(plan)}>
                  Confirm + create branch
                </button>
              )}
            </div>
            {previews[plan.id] && (
              <details>
                <summary>Preview payload</summary>
                <pre className="output">{JSON.stringify(previews[plan.id].payload_json, null, 2)}</pre>
              </details>
            )}
            {results[plan.id] && (
              <p className={results[plan.id].status === "completed" ? "" : "warn"}>
                GitHub: {results[plan.id].status} {results[plan.id].error_message}
              </p>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}

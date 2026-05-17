"use client";

import { useEffect, useState } from "react";
import { BranchPlan, GitHubWriteEvent, PRPacket, Repository, Task, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function PRPacketsPage({ params }: { params: { id: string } }) {
  const [packets, setPackets] = useState<PRPacket[]>([]);
  const [plans, setPlans] = useState<BranchPlan[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [planId, setPlanId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [title, setTitle] = useState("");
  const [previews, setPreviews] = useState<Record<string, GitHubWriteEvent>>({});
  const [results, setResults] = useState<Record<string, GitHubWriteEvent>>({});

  async function load() {
    const [repos, branchPlans, taskItems, prItems] = await Promise.all([
      api.repositories(params.id),
      api.branchPlans(params.id),
      api.tasks(params.id),
      api.prPackets(params.id)
    ]);
    setRepositories(repos);
    setPlans(branchPlans);
    setTasks(taskItems);
    setPackets(prItems);
    if (!repositoryId && repos[0]) setRepositoryId(repos[0].id);
  }
  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!repositoryId) return;
    await api.generatePRPacket(params.id, {
      repository_id: repositoryId,
      branch_plan_id: planId || undefined,
      task_id: taskId || undefined,
      title
    });
    await load();
  }

  async function previewPR(packet: PRPacket) {
    setPreviews({ ...previews, [packet.id]: await api.githubPreviewDraftPR(params.id, packet.id) });
  }

  async function createPR(packet: PRPacket) {
    try {
      const event = await api.githubCreateDraftPR(params.id, packet.id, { approved: true, dry_run: false });
      setResults({ ...results, [packet.id]: event });
      await load();
    } catch (err) {
      setResults({
        ...results,
        [packet.id]: {
          id: "local",
          project_id: params.id,
          entity_type: "pr_packet",
          entity_id: packet.id,
          action: "create_draft_pr",
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
        <div className="eyebrow">PR Handoff</div>
        <h1>PR Packets</h1>
        <p>PR-ready summaries plus optional draft-only GitHub PR creation under explicit approval.</p>
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
            <span>Branch plan</span>
            <select value={planId} onChange={(e) => setPlanId(e.target.value)}>
              <option value="">None</option>
              {plans.map((plan) => (
                <option value={plan.id} key={plan.id}>
                  {plan.objective}
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
        </div>
        <label className="field">
          <span>Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <button className="button" onClick={generate}>
          Generate PR packet
        </button>
      </section>
      <section className="stack">
        {packets.map((packet) => (
          <article className="card stack" key={packet.id}>
            <h2>{packet.title}</h2>
            <p>{packet.summary}</p>
            <div className="output">
              {[
                "Changes:",
                ...packet.changes_expected.map((c) => `- ${c}`),
                "",
                "Tests:",
                ...packet.test_plan.map((t) => `- ${t}`),
                "",
                "Checklist:",
                ...packet.acceptance_checklist.map((a) => `- [ ] ${a}`),
                "",
                packet.reviewer_notes
              ].join("\n")}
            </div>
            {packet.github_pr_url && (
              <p>
                PR: <a href={packet.github_pr_url}>#{packet.github_pr_number}</a> ({packet.github_sync_status})
              </p>
            )}
            <div className="row">
              <button className="button secondary" onClick={() => previewPR(packet)}>
                Preview draft PR
              </button>
              {previews[packet.id] && (
                <button className="button" onClick={() => createPR(packet)}>
                  Confirm + create draft PR
                </button>
              )}
            </div>
            {previews[packet.id] && (
              <details>
                <summary>Preview payload</summary>
                <pre className="output">{JSON.stringify(previews[packet.id].payload_json, null, 2)}</pre>
              </details>
            )}
            {results[packet.id] && (
              <p className={results[packet.id].status === "completed" ? "" : "warn"}>
                GitHub: {results[packet.id].status} {results[packet.id].error_message}
              </p>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}

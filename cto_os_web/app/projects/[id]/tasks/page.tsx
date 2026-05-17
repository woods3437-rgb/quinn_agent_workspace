"use client";

import { FormEvent, useEffect, useState } from "react";
import { Plus, Wand2, X } from "lucide-react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { api, GitHubWriteEvent, Task } from "@/lib/api";

const statuses: Task["status"][] = ["backlog", "todo", "in_progress", "blocked", "review", "done"];
const priorities: Task["priority"][] = ["low", "medium", "high", "urgent"];
const categories: Task["category"][] = ["product", "design", "frontend", "backend", "data", "ai", "growth", "research", "ops"];

type TaskDraft = Omit<Task, "id" | "project_id" | "created_at" | "updated_at">;

const emptyTask: TaskDraft = {
  title: "",
  description: "",
  status: "backlog" as const,
  priority: "medium" as const,
  category: "product" as const,
  acceptance_criteria: [] as string[],
  dependencies: [] as string[],
  linked_memory_ids: [] as string[],
  linked_decision_ids: [] as string[],
  linked_output_ids: [] as string[]
};

export default function TasksPage({ params }: { params: { id: string } }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [form, setForm] = useState<TaskDraft>({ ...emptyTask });
  const [criteria, setCriteria] = useState("");
  const [links, setLinks] = useState({ memory: "", decision: "", output: "" });
  const [plan, setPlan] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [executionResult, setExecutionResult] = useState("");
  const [errorLogs, setErrorLogs] = useState("");
  const [review, setReview] = useState("");
  const [githubPreview, setGithubPreview] = useState<GitHubWriteEvent | null>(null);
  const [githubResult, setGithubResult] = useState<GitHubWriteEvent | null>(null);

  async function previewIssue(task: Task) {
    setGithubResult(null);
    setGithubPreview(await api.githubPreviewTaskIssue(params.id, task.id));
  }

  async function createIssue(task: Task) {
    if (!githubPreview) return;
    try {
      setGithubResult(
        await api.githubCreateTaskIssue(params.id, task.id, { approved: true, dry_run: false })
      );
    } catch (err) {
      setGithubResult({
        id: "local",
        project_id: params.id,
        entity_type: "task",
        entity_id: task.id,
        action: "create_issue",
        dry_run: false,
        approved: true,
        payload_json: {},
        response_json: {},
        status: "failed",
        error_message: String((err as Error).message ?? err),
        created_at: new Date().toISOString()
      });
    }
  }

  async function load() {
    setTasks(await api.tasks(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  async function createTask(event: FormEvent) {
    event.preventDefault();
    await api.createTask(params.id, { ...form, acceptance_criteria: criteria.split("\n").map((item) => item.trim()).filter(Boolean) });
    setForm({ ...emptyTask });
    setCriteria("");
    await load();
  }

  async function updateTask(task: Task, patch: Partial<Task>) {
    const updated = await api.updateTask(params.id, task.id, patch);
    setSelected(updated);
    await load();
  }

  async function generatePlan(task: Task) {
    const output = await api.generateImplementationPlan(params.id, { source_type: "task", source_id: task.id, save_output: true });
    setPlan(output.output);
  }

  async function reviewImplementation(task: Task) {
    const result = await api.createImplementationReview(params.id, {
      task_id: task.id,
      attempted: true,
      execution_result: executionResult,
      error_logs: errorLogs,
      implementation_notes: reviewNotes,
      save_lesson_to_memory: true,
      create_follow_up_tasks: true
    });
    setReview(result.review_result);
  }

  async function linkSelected() {
    if (!selected) return;
    await updateTask(selected, {
      linked_memory_ids: links.memory ? [...selected.linked_memory_ids, links.memory] : selected.linked_memory_ids,
      linked_decision_ids: links.decision ? [...selected.linked_decision_ids, links.decision] : selected.linked_decision_ids,
      linked_output_ids: links.output ? [...selected.linked_output_ids, links.output] : selected.linked_output_ids
    });
    setLinks({ memory: "", decision: "", output: "" });
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Task System</div><h1>Tasks</h1><p>Internal Kanban for turning memory, roadmaps, decisions, and outputs into execution.</p></div>
      <ProjectTabs projectId={params.id} />
      <form className="panel stack" onSubmit={createTask}>
        <h2>New Task</h2>
        <label className="field"><span>Title</span><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label className="field"><span>Description</span><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <div className="grid">
          <label className="field"><span>Priority</span><select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Task["priority"] })}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="field"><span>Category</span><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as Task["category"] })}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        <label className="field"><span>Acceptance criteria</span><textarea value={criteria} onChange={(e) => setCriteria(e.target.value)} placeholder="One criterion per line" /></label>
        <button className="button row" type="submit"><Plus size={17} /> Add task</button>
      </form>
      <section className="kanban">
        {statuses.map((status) => (
          <div className="kanban-column" key={status}>
            <h3>{status.replace("_", " ")}</h3>
            {tasks.filter((task) => task.status === status).map((task) => (
              <button className="task-card" key={task.id} onClick={() => setSelected(task)}>
                <span className={`priority ${task.priority}`}>{task.priority}</span>
                <strong>{task.title}</strong>
                <small>{task.category}</small>
              </button>
            ))}
          </div>
        ))}
      </section>
      {selected && (
        <div className="drawer">
          <div className="drawer-panel stack">
            <div className="spread"><h2>{selected.title}</h2><button className="button secondary" onClick={() => setSelected(null)}><X size={17} /></button></div>
            <p>{selected.description}</p>
            <div className="grid">
              <label className="field"><span>Status</span><select value={selected.status} onChange={(e) => updateTask(selected, { status: e.target.value as Task["status"] })}>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label className="field"><span>Priority</span><select value={selected.priority} onChange={(e) => updateTask(selected, { priority: e.target.value as Task["priority"] })}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
            </div>
            <div className="grid">
              <label className="field"><span>Memory id</span><input value={links.memory} onChange={(e) => setLinks({ ...links, memory: e.target.value })} /></label>
              <label className="field"><span>Decision id</span><input value={links.decision} onChange={(e) => setLinks({ ...links, decision: e.target.value })} /></label>
              <label className="field"><span>Output id</span><input value={links.output} onChange={(e) => setLinks({ ...links, output: e.target.value })} /></label>
            </div>
            <div className="row"><button className="button secondary" onClick={linkSelected}>Link artifacts</button><button className="button row" onClick={() => generatePlan(selected)}><Wand2 size={17} /> Implementation plan</button></div>
            <div className="output">{plan || selected.acceptance_criteria.map((item) => `- ${item}`).join("\n")}</div>
            <button className="button secondary" onClick={() => updateTask(selected, { status: "review" })}>Mark attempted</button>
            <label className="field"><span>Execution result</span><textarea value={executionResult} onChange={(e) => setExecutionResult(e.target.value)} /></label>
            <label className="field"><span>Error logs</span><textarea value={errorLogs} onChange={(e) => setErrorLogs(e.target.value)} /></label>
            <label className="field"><span>Implementation notes</span><textarea value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} /></label>
            <button className="button secondary" onClick={() => reviewImplementation(selected)}>Review implementation</button>
            {review && <div className="output">{review}</div>}
            <div className="stack">
              <h3>GitHub Issue</h3>
              {selected.github_issue_url && (
                <p>
                  Linked: <a href={selected.github_issue_url}>#{selected.github_issue_number}</a> ({selected.github_sync_status})
                </p>
              )}
              <div className="row">
                <button className="button secondary" onClick={() => previewIssue(selected)}>Preview issue payload</button>
                {githubPreview && (
                  <button className="button" onClick={() => createIssue(selected)}>
                    Confirm + create issue
                  </button>
                )}
              </div>
              {githubPreview && (
                <details open>
                  <summary>Preview payload (no GitHub call yet)</summary>
                  <pre className="output">{JSON.stringify(githubPreview.payload_json, null, 2)}</pre>
                </details>
              )}
              {githubResult && (
                <p className={githubResult.status === "completed" ? "" : "warn"}>
                  GitHub result: {githubResult.status} {githubResult.error_message}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

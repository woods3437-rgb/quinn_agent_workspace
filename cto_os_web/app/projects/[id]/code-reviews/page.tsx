"use client";

import { useEffect, useState } from "react";
import { BranchPlan, CodeReview, Repository, Task, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function CodeReviewsPage({ params }: { params: { id: string } }) {
  const [reviews, setReviews] = useState<CodeReview[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [plans, setPlans] = useState<BranchPlan[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [taskId, setTaskId] = useState("");
  const [planId, setPlanId] = useState("");
  const [diff, setDiff] = useState("");

  async function load() {
    const [repoItems, taskItems, planItems, reviewItems] = await Promise.all([api.repositories(params.id), api.tasks(params.id), api.branchPlans(params.id), api.codeReviews(params.id)]);
    setRepositories(repoItems); setTasks(taskItems); setPlans(planItems); setReviews(reviewItems);
    if (!repositoryId && repoItems[0]) setRepositoryId(repoItems[0].id);
  }
  useEffect(() => { load(); }, []);

  async function review() {
    await api.createCodeReview(params.id, { repository_id: repositoryId || undefined, task_id: taskId || undefined, branch_plan_id: planId || undefined, diff_text: diff, create_follow_up_tasks: true });
    setDiff("");
    await load();
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Safe Diff Review</div><h1>Code Reviews</h1><p>Paste diffs or patch text for internal review. No commits, pushes, or PR mutations.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <div className="grid">
          <label className="field"><span>Repository</span><select value={repositoryId} onChange={(e) => setRepositoryId(e.target.value)}><option value="">None</option>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select></label>
          <label className="field"><span>Task</span><select value={taskId} onChange={(e) => setTaskId(e.target.value)}><option value="">None</option>{tasks.map((task) => <option value={task.id} key={task.id}>{task.title}</option>)}</select></label>
          <label className="field"><span>Branch plan</span><select value={planId} onChange={(e) => setPlanId(e.target.value)}><option value="">None</option>{plans.map((plan) => <option value={plan.id} key={plan.id}>{plan.objective}</option>)}</select></label>
        </div>
        <label className="field"><span>Diff / patch text</span><textarea value={diff} onChange={(e) => setDiff(e.target.value)} /></label>
        <button className="button" onClick={review}>Review diff</button>
      </section>
      <section className="stack">{reviews.map((review) => <article className="card stack" key={review.id}><div className="spread"><h2>{review.approval_recommendation}</h2><span className="badge">{review.risk_level}</span></div><p>{review.review_summary}</p><div className="output">{review.findings.map((f) => `- ${f}`).join("\n")}</div></article>)}</section>
    </div>
  );
}

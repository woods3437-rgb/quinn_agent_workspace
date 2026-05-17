"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { BuildSession, PostShipRetrospective, api } from "@/lib/api";

export default function RetrospectivesPage({ params }: { params: { id: string } }) {
  const [retros, setRetros] = useState<PostShipRetrospective[]>([]);
  const [sessions, setSessions] = useState<BuildSession[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [saveLessons, setSaveLessons] = useState(true);
  const [createDecision, setCreateDecision] = useState(true);
  const [createFollowUps, setCreateFollowUps] = useState(true);
  const [pin, setPin] = useState(false);

  async function load() {
    const [list, allSessions] = await Promise.all([
      api.retrospectives(params.id),
      api.buildSessions(params.id)
    ]);
    setRetros(list);
    setSessions(allSessions);
    if (!sessionId && allSessions[0]) setSessionId(allSessions[0].id);
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    if (!sessionId) return;
    await api.generateRetrospective(params.id, {
      build_session_id: sessionId,
      save_lessons_to_memory: saveLessons,
      create_decision: createDecision,
      create_follow_up_tasks: createFollowUps,
      pin_to_source_of_truth: pin
    });
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Lifecycle Loop</div>
        <h1>Retrospectives</h1>
        <p>Post-ship retrospectives feed lessons back into memory, decisions, and follow-up tasks.</p>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <label className="field">
          <span>Build session</span>
          <select value={sessionId} onChange={(event) => setSessionId(event.target.value)}>
            {sessions.map((session) => (
              <option value={session.id} key={session.id}>
                {session.title} ({session.status})
              </option>
            ))}
          </select>
        </label>
        <div className="row">
          <label className="field">
            <span>Save lessons</span>
            <input type="checkbox" checked={saveLessons} onChange={(event) => setSaveLessons(event.target.checked)} />
          </label>
          <label className="field">
            <span>Create decision</span>
            <input type="checkbox" checked={createDecision} onChange={(event) => setCreateDecision(event.target.checked)} />
          </label>
          <label className="field">
            <span>Create follow-up tasks</span>
            <input type="checkbox" checked={createFollowUps} onChange={(event) => setCreateFollowUps(event.target.checked)} />
          </label>
          <label className="field">
            <span>Pin as source-of-truth</span>
            <input type="checkbox" checked={pin} onChange={(event) => setPin(event.target.checked)} />
          </label>
        </div>
        <button className="button" onClick={generate} disabled={!sessionId}>
          Generate retrospective
        </button>
      </section>
      <section className="stack">
        {retros.length === 0 && <p>No retrospectives yet.</p>}
        {retros.map((retro) => (
          <article className="card stack" key={retro.id}>
            <h2>{retro.title}</h2>
            <p>{retro.summary}</p>
            <div className="grid">
              <div>
                <h3>What changed</h3>
                <ul>
                  {retro.what_changed.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>What worked</h3>
                <ul>
                  {retro.what_worked.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>What broke</h3>
                <ul>
                  {retro.what_broke.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
            <p>
              <strong>Tests:</strong> {retro.test_results}
            </p>
            {retro.lessons_learned && (
              <p>
                <strong>Lessons:</strong> {retro.lessons_learned}
              </p>
            )}
            <p>
              <small>
                Memories saved: {retro.memory_ids_created.length} · Decisions: {retro.decision_ids_created.length} ·
                Follow-up tasks: {retro.follow_up_task_ids.length}
              </small>
            </p>
          </article>
        ))}
      </section>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { OutcomeScore, OutcomeScoreType, api } from "@/lib/api";

const TYPES: OutcomeScoreType[] = [
  "retrospective_accuracy",
  "decision_quality",
  "risk_prediction",
  "execution_quality"
];

export default function ProjectOutcomesPage({ params }: { params: { id: string } }) {
  const [scores, setScores] = useState<OutcomeScore[]>([]);
  const [scoreType, setScoreType] = useState<OutcomeScoreType>("execution_quality");
  const [score, setScore] = useState(3);
  const [notes, setNotes] = useState("");

  async function load() {
    setScores(await api.outcomeScores(params.id));
  }

  useEffect(() => {
    load();
  }, []);

  async function submit() {
    await api.createOutcomeScore(params.id, { score_type: scoreType, score, notes });
    setNotes("");
    await load();
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Project</div>
        <h1>Outcomes</h1>
      </div>
      <ProjectTabs projectId={params.id} />
      <section className="panel stack">
        <h2>Record a score</h2>
        <label className="field">
          <span>Type</span>
          <select value={scoreType} onChange={(e) => setScoreType(e.target.value as OutcomeScoreType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Score (1–5)</span>
          <input
            type="number"
            min={1}
            max={5}
            value={score}
            onChange={(e) => setScore(Number(e.target.value))}
          />
        </label>
        <label className="field">
          <span>Notes</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <button className="button" onClick={submit}>
          Save score
        </button>
      </section>
      <section className="stack">
        {scores.map((s) => (
          <article className="card" key={s.id}>
            <strong>{s.score_type}</strong>: {s.score}/5 — {s.notes || "(no notes)"}
          </article>
        ))}
        {scores.length === 0 && <p>No outcome scores yet.</p>}
      </section>
    </div>
  );
}

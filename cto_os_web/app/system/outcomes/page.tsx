"use client";

import { useEffect, useState } from "react";
import { OutcomeScore, api } from "@/lib/api";

export default function SystemOutcomesPage() {
  const [scores, setScores] = useState<OutcomeScore[]>([]);

  useEffect(() => {
    api.systemOutcomeScores().then(setScores);
  }, []);

  const byType: Record<string, OutcomeScore[]> = {};
  for (const score of scores) {
    (byType[score.score_type] ??= []).push(score);
  }

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>Outcome Scores</h1>
      </div>
      {Object.entries(byType).map(([kind, items]) => {
        const avg = items.reduce((sum, s) => sum + s.score, 0) / items.length;
        return (
          <article className="card stack" key={kind}>
            <h2>
              {kind} — {avg.toFixed(2)} avg over {items.length} sample(s)
            </h2>
            <ul>
              {items.map((score) => (
                <li key={score.id}>
                  {score.score}/5 · {score.notes || "(no notes)"}
                </li>
              ))}
            </ul>
          </article>
        );
      })}
      {scores.length === 0 && <p>No scores recorded yet.</p>}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Playbook, api } from "@/lib/api";

export default function SystemPlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);

  useEffect(() => {
    api.systemPlaybooks().then(setPlaybooks);
  }, []);

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>Playbooks</h1>
        <p>Reusable templates distilled from completed build sessions.</p>
      </div>
      {playbooks.length === 0 && <p>No playbooks yet. Generate one from a completed build session.</p>}
      {playbooks.map((playbook) => (
        <article className="card stack" key={playbook.id}>
          <div className="spread">
            <h2>{playbook.name}</h2>
            <span className="badge">{playbook.category}</span>
          </div>
          <p>{playbook.description}</p>
          <h3>Steps</h3>
          <ol>
            {playbook.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          {playbook.acceptance_criteria.length > 0 && (
            <>
              <h3>Acceptance criteria</h3>
              <ul>
                {playbook.acceptance_criteria.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </>
          )}
        </article>
      ))}
    </div>
  );
}

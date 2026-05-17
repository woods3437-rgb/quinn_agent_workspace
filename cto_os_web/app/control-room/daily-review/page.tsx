"use client";

import { useEffect, useState } from "react";
import { DailyReview, api } from "@/lib/api";

export default function DailyReviewPage() {
  const [review, setReview] = useState<DailyReview | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      setReview(await api.generateDailyReview());
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Control Room</div>
        <h1>Daily Review</h1>
        <p>Aggregated brief grounded in CTO OS state. Read first thing in the morning.</p>
        <button className="button" onClick={load} disabled={busy}>
          Regenerate
        </button>
      </div>
      {!review && <p>Loading…</p>}
      {review && (
        <>
          <section className="panel">
            <strong>{review.headline}</strong>
            <p>
              <small>Generated {new Date(review.generated_at).toLocaleString()}</small>
            </p>
          </section>
          <section className="panel">
            <h2>Markdown brief</h2>
            <pre className="output">{review.markdown}</pre>
          </section>
          <section className="stack">
            <h2>Recommended next actions</h2>
            <ul>
              {review.recommended_next_actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

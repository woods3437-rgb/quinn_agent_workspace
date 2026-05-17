"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { GeneratedOutput, api } from "@/lib/api";

export default function OutputsPage({ params }: { params: { id: string } }) {
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [reviews, setReviews] = useState<Record<string, string>>({});

  useEffect(() => {
    api.outputs(params.id).then(setOutputs);
  }, []);

  async function review(output: GeneratedOutput) {
    const result = await api.createImplementationReview(params.id, {
      output_id: output.id,
      attempted: true,
      execution_result: results[output.id] ?? "",
      error_logs: errors[output.id] ?? "",
      implementation_notes: notes[output.id] ?? "",
      save_lesson_to_memory: true,
      create_follow_up_tasks: true
    });
    setReviews({ ...reviews, [output.id]: result.review_result });
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Prompt / Output Generator</div><h1>Outputs</h1><p>Saved generated outputs for this project.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="stack">
        {outputs.map((output) => (
          <article className="card stack" key={output.id}>
            <div className="spread"><h2>{output.agent_id}</h2><span className="muted">{new Date(output.created_at).toLocaleString()}</span></div>
            <div className="output">{output.output}</div>
            <label className="field"><span>Execution result</span><textarea value={results[output.id] ?? ""} onChange={(e) => setResults({ ...results, [output.id]: e.target.value })} /></label>
            <label className="field"><span>Error logs</span><textarea value={errors[output.id] ?? ""} onChange={(e) => setErrors({ ...errors, [output.id]: e.target.value })} /></label>
            <label className="field"><span>Implementation notes</span><textarea value={notes[output.id] ?? ""} onChange={(e) => setNotes({ ...notes, [output.id]: e.target.value })} /></label>
            <button className="button secondary" onClick={() => review(output)}>Review implementation</button>
            {reviews[output.id] && <div className="output">{reviews[output.id]}</div>}
          </article>
        ))}
      </section>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { DecisionGraph, api } from "@/lib/api";

export default function SystemDecisionGraphPage() {
  const [graph, setGraph] = useState<DecisionGraph | null>(null);

  useEffect(() => {
    api.systemDecisionGraph().then(setGraph);
  }, []);

  if (!graph) return <p>Loading…</p>;

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">System</div>
        <h1>Decision Graph</h1>
        <p>{graph.nodes.length} nodes · {graph.edges.length} edges</p>
      </div>
      <section className="stack">
        <h2>Nodes</h2>
        {graph.nodes.map((node) => (
          <article className="card" key={node.id}>
            <strong>{node.title}</strong> <small>({node.kind} · {node.project_id ?? ""})</small>
          </article>
        ))}
      </section>
      <section className="stack">
        <h2>Edges</h2>
        <ul>
          {graph.edges.map((edge, i) => (
            <li key={`${edge.source}-${edge.target}-${i}`}>
              <code>{edge.source}</code> — {edge.relation} → <code>{edge.target}</code>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

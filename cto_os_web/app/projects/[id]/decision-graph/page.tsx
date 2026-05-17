"use client";

import { useEffect, useState } from "react";
import { ProjectTabs } from "@/components/ProjectTabs";
import { DecisionGraph, api } from "@/lib/api";

export default function ProjectDecisionGraphPage({ params }: { params: { id: string } }) {
  const [graph, setGraph] = useState<DecisionGraph | null>(null);

  useEffect(() => {
    api.projectDecisionGraph(params.id).then(setGraph);
  }, []);

  return (
    <div className="stack">
      <div>
        <div className="eyebrow">Project</div>
        <h1>Decision Graph</h1>
      </div>
      <ProjectTabs projectId={params.id} />
      {!graph && <p>Loading…</p>}
      {graph && (
        <>
          <section className="stack">
            <h2>Nodes ({graph.nodes.length})</h2>
            {graph.nodes.map((node) => (
              <article className="card" key={node.id}>
                <strong>{node.title}</strong> <small>({node.kind})</small>
              </article>
            ))}
          </section>
          <section className="stack">
            <h2>Edges ({graph.edges.length})</h2>
            <ul>
              {graph.edges.map((edge, i) => (
                <li key={`${edge.source}-${edge.target}-${i}`}>
                  <code>{edge.source}</code> {edge.relation} <code>{edge.target}</code>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

import { api } from "@/lib/api";
import { ProjectHeader } from "@/components/ProjectHeader";
import Link from "next/link";

export default async function ProjectOverview({ params }: { params: { id: string } }) {
  const [memories, decisions, outputs] = await Promise.all([
    api.memories(params.id),
    api.decisions(params.id),
    api.outputs(params.id)
  ]);

  return (
    <div>
      <ProjectHeader projectId={params.id} />
      <div className="row" style={{ marginBottom: 16 }}>
        <Link className="button" href={`/projects/${params.id}/weekly-brief`}>Generate Weekly CTO Brief</Link>
        <Link className="button secondary" href={`/projects/${params.id}/workflows`}>Run workflow</Link>
        <Link className="button secondary" href={`/projects/${params.id}/build-packets`}>Create build packet</Link>
      </div>
      <section className="grid">
        <div className="card">
          <h2>{memories.length}</h2>
          <p>Project memories</p>
        </div>
        <div className="card">
          <h2>{memories.filter((memory) => memory.pinned).length}</h2>
          <p>Pinned source-of-truth memories</p>
        </div>
        <div className="card">
          <h2>{decisions.length}</h2>
          <p>Logged decisions</p>
        </div>
        <div className="card">
          <h2>{outputs.length}</h2>
          <p>Saved generated outputs</p>
        </div>
      </section>
    </div>
  );
}

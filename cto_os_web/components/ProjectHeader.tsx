import { api } from "@/lib/api";
import { ProjectTabs } from "./ProjectTabs";

export async function ProjectHeader({ projectId }: { projectId: string }) {
  const project = await api.project(projectId);
  return (
    <>
      <div className="topline">
        <div>
          <div className="eyebrow">Project Command Center</div>
          <h1>{project.name}</h1>
          <p>{project.description || "No description added yet."}</p>
        </div>
        <span className="badge">{project.status}</span>
      </div>
      <ProjectTabs projectId={projectId} />
    </>
  );
}

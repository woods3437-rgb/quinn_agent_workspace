import Link from "next/link";

export function ProjectTabs({ projectId }: { projectId: string }) {
  const base = `/projects/${projectId}`;
  return (
    <nav className="tabs">
      <Link href={base}>Overview</Link>
      <Link href={`${base}/memory`}>Memory</Link>
      <Link href={`${base}/decisions`}>Decisions</Link>
      <Link href={`${base}/architecture`}>Architecture</Link>
      <Link href={`${base}/roadmap`}>Roadmap</Link>
      <Link href={`${base}/tasks`}>Tasks</Link>
      <Link href={`${base}/workflows`}>Workflows</Link>
      <Link href={`${base}/jobs`}>Jobs</Link>
      <Link href={`${base}/build-packets`}>Build Packets</Link>
      <Link href={`${base}/branch-plans`}>Branch Plans</Link>
      <Link href={`${base}/pr-packets`}>PR Packets</Link>
      <Link href={`${base}/code-reviews`}>Code Reviews</Link>
      <Link href={`${base}/test-runs`}>Test Runs</Link>
      <Link href={`${base}/commands`}>Commands</Link>
      <Link href={`${base}/build-sessions`}>Build Sessions</Link>
      <Link href={`${base}/symbols`}>Symbols</Link>
      <Link href={`${base}/github-events`}>GitHub Events</Link>
      <Link href={`${base}/status-suggestions`}>Suggestions</Link>
      <Link href={`${base}/retrospectives`}>Retrospectives</Link>
      <Link href={`${base}/shipped`}>Shipped</Link>
      <Link href={`${base}/decision-graph`}>Decision Graph</Link>
      <Link href={`${base}/playbooks`}>Playbooks</Link>
      <Link href={`${base}/outcomes`}>Outcomes</Link>
      <Link href={`${base}/mcp-audit`}>MCP Audit</Link>
      <Link href={`${base}/brief`}>Brief</Link>
      <Link href={`${base}/risks`}>Risks</Link>
      <Link href={`${base}/logs`}>Logs</Link>
      <Link href={`${base}/workspace`}>Workspace</Link>
      <Link href={`${base}/prompts`}>Prompts</Link>
      <Link href={`${base}/repositories`}>Repositories</Link>
      <Link href={`${base}/outputs`}>Outputs</Link>
      <Link href={`${base}/weekly-brief`}>Weekly</Link>
    </nav>
  );
}

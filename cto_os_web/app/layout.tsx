import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Private CTO OS",
  description: "Internal founder brain powered by project memory"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">Founder Brain</div>
            <nav className="nav">
              <Link href="/projects">Projects</Link>
              <Link href="/control-room">Control Room</Link>
              <Link href="/control-room/daily-review">Daily Review</Link>
              <Link href="/system/health">Health</Link>
              <Link href="/system/mcp-audit">MCP Audit</Link>
              <Link href="/system/mcp-sessions">MCP Sessions</Link>
              <Link href="/system/shipped">System Shipped</Link>
              <Link href="/system/risks">System Risks</Link>
              <Link href="/system/decision-graph">Decision Graph</Link>
              <Link href="/system/playbooks">Playbooks</Link>
              <Link href="/system/outcomes">Outcomes</Link>
              <Link href="/settings">Settings</Link>
              <Link href="/settings/notifications">Notifications</Link>
              <Link href="/settings/intake">Intake</Link>
              <Link href="/settings/backups">Backups</Link>
              <Link href="/settings/cron">Cron</Link>
              <Link href="/settings/retention">Retention</Link>
              <Link href="/settings/health-alerts">Health Alerts</Link>
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

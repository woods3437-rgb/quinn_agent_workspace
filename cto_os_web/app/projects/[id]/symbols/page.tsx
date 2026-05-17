"use client";

import { useEffect, useState } from "react";
import { CodeDependency, CodeSymbol, Repository, api } from "@/lib/api";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function SymbolsPage({ params }: { params: { id: string } }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [repositoryId, setRepositoryId] = useState("");
  const [symbols, setSymbols] = useState<CodeSymbol[]>([]);
  const [dependencies, setDependencies] = useState<CodeDependency[]>([]);
  const [query, setQuery] = useState("");

  async function load(repoId = repositoryId) {
    const repos = await api.repositories(params.id);
    setRepositories(repos);
    const active = repoId || repos[0]?.id || "";
    setRepositoryId(active);
    if (active) {
      setSymbols(await api.codeSymbols(params.id, active));
      setDependencies(await api.codeDependencies(params.id, active));
    }
  }
  useEffect(() => { load(); }, []);

  async function search() {
    if (repositoryId) setSymbols(await api.searchCodeSymbols(params.id, repositoryId, query));
  }

  return (
    <div className="stack">
      <div><div className="eyebrow">Code Intelligence</div><h1>Symbols</h1><p>Functions, classes, exports, route handlers, components, imports, and dependencies from repo scans.</p></div>
      <ProjectTabs projectId={params.id} />
      <section className="panel row">
        <select value={repositoryId} onChange={(e) => load(e.target.value)}>{repositories.map((repo) => <option value={repo.id} key={repo.id}>{repo.name}</option>)}</select>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search symbols" />
        <button className="button secondary" onClick={search}>Search</button>
      </section>
      <section className="grid">
        <article className="panel stack"><h2>Symbols</h2>{symbols.slice(0, 200).map((symbol) => <div className="card" key={symbol.id}><strong>{symbol.name}</strong><p>{symbol.symbol_type} · {symbol.file_path}:{symbol.line_start ?? ""}</p></div>)}</article>
        <article className="panel stack"><h2>Dependencies</h2>{dependencies.slice(0, 200).map((dep) => <div className="card" key={dep.id}><strong>{dep.dependency}</strong><p>{dep.file_path}</p></div>)}</article>
      </section>
    </div>
  );
}

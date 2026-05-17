# Phase 1 Audit: Founder Brain CTO OS

## Repository State

The MemPalace source (originally distributed as `mempalace-main.zip`) has been merged into the workspace root. The existing package remains intact:

- `mempalace/cli.py`: command-line entrypoint.
- `mempalace/mcp_server.py`: MCP server surface.
- `mempalace/miner.py`: project file mining into ChromaDB.
- `mempalace/convo_miner.py`: conversation mining.
- `mempalace/searcher.py`: ChromaDB semantic search.
- `mempalace/config.py`: local config and default palace path.
- `hooks/`, `.agents/`, `.codex-plugin/`, `.claude-plugin/`, and `.github/` are present at the workspace root.

Phase 1 is implemented as an additive CTO OS layer. It does not remove or rewrite the MemPalace CLI, MCP server, miners, hooks, or tests.

## Target Architecture

- Existing MemPalace package remains the memory engine.
- `cto_os_api/` provides a private FastAPI layer for projects, memories, decisions, agents, prompt templates, and generated outputs.
- `cto_os_web/` provides a private Next.js command-center UI.
- Local-first data is stored in `cto_os_api/data/cto_os.json` by default.
- Project-scoped retrieval is the default. Cross-project search requires an explicit `cross_project=true` API parameter.
- CTO OS maps each `project_id` to a MemPalace `wing`.

## Memory Storage And Retrieval

Implemented Phase 1 behavior:

- Memories belong to exactly one `project_id`.
- Pinned memories are marked with `pinned: true` and treated as source-of-truth context.
- Retrieval defaults to the active project's MemPalace `wing`.
- Cross-project retrieval only runs when explicitly requested.
- Generated outputs can be saved back as project memories.

MemPalace integration:

- `cto_os_api/memory_engine.py` now uses `MempalaceMemoryEngine`.
- New CTO OS memories are indexed into ChromaDB using MemPalace's `mempalace_drawers` collection.
- `project_id` is stored as both the MemPalace `wing` and explicit metadata.
- Pinned memories are indexed into the `source_of_truth` room.
- Default search passes `wing=project_id`, preserving project isolation.
- Explicit cross-project search omits the wing filter.
- If ChromaDB or MemPalace dependencies are unavailable, the engine falls back to local JSON search.
- Chroma's ONNX model cache is redirected to `cto_os_api/data/chroma_cache` by default so it stays inside the workspace.

## Reusable CTO OS Modules

- `cto_os_api/storage.py`: local JSON persistence and project-scoped data access.
- `cto_os_api/memory_engine.py`: retrieval boundary for MemPalace integration.
- `cto_os_api/prompting.py`: prompt and output generation orchestration.
- `cto_os_api/agents.py`: default private founder/CTO agent definitions.
- `cto_os_web/lib/api.ts`: frontend API client.
- `cto_os_web/components/*`: reusable command-center UI pieces.

## Security And Architecture Notes

- This is intentionally private/internal-only. No billing, public signup, or tenant marketplace is included.
- There is no production authentication in Phase 1. Put the app behind VPN, localhost, or an internal auth proxy before real use.
- CORS currently defaults to localhost development origins. Set `CTO_OS_CORS_ORIGINS` for deployed internal environments.
- Local JSON storage is useful for Phase 1 but should be backed up. For heavier internal use, replace it with SQLite or Postgres while keeping the API contract.
- The first MemPalace/Chroma semantic operation downloads the local ONNX embedding model. In this implementation, that cache is kept under `cto_os_api/data/chroma_cache` unless `CTO_OS_CHROMA_CACHE_DIR` is set.
- AI generation is deterministic template assembly in this scaffold. Wire model calls behind `PromptService.generate_output` if needed.

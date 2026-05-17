from __future__ import annotations

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from pathlib import Path

from .models import Memory
from .storage import JsonStore


class LocalMemoryEngine:
    """Project-scoped retrieval boundary with local fallback search."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    @property
    def backend_name(self) -> str:
        return "local-json"

    def index_memory(self, memory: Memory) -> None:
        """Index a memory in the retrieval backend."""
        return None

    def search(self, project_id: str, query: str = "", cross_project: bool = False, limit: int = 8) -> list[Memory]:
        memories = self.store.list_memories(project_id=None if cross_project else project_id)
        if not query.strip():
            return memories[:limit]

        terms = {term.lower() for term in query.split() if term.strip()}

        def score(memory: Memory) -> int:
            haystack = f"{memory.title} {memory.content} {' '.join(memory.tags)}".lower()
            pin_boost = 3 if memory.pinned and memory.project_id == project_id else 0
            return pin_boost + sum(1 for term in terms if term in haystack)

        ranked = sorted(memories, key=lambda memory: (score(memory), memory.updated_at), reverse=True)
        return [memory for memory in ranked if score(memory) > 0 or memory.pinned][:limit]

    def pinned_context(self, project_id: str) -> list[Memory]:
        return self.store.list_memories(project_id=project_id, pinned=True)


class MempalaceMemoryEngine(LocalMemoryEngine):
    """MemPalace-backed semantic retrieval for CTO OS project memory.

    CTO OS maps each private project to a MemPalace wing using the stable
    `project_id`. Rooms remain lightweight CTO OS categories.
    """

    def __init__(self, store: JsonStore, palace_path: str | None = None) -> None:
        super().__init__(store)
        self.palace_path = os.path.expanduser(
            palace_path
            or os.getenv("CTO_OS_MEMPALACE_PATH")
            or os.getenv("MEMPALACE_PALACE_PATH")
            or os.getenv("MEMPAL_PALACE_PATH")
            or str(Path.home() / ".mempalace" / "palace")
        )
        self.chroma_cache_dir = Path(
            os.getenv(
                "CTO_OS_CHROMA_CACHE_DIR",
                str(Path(__file__).parent / "data" / "chroma_cache"),
            )
        )
        self._available = self._check_available()

    @property
    def backend_name(self) -> str:
        return "mempalace-chromadb" if self._available else "local-json"

    def _check_available(self) -> bool:
        try:
            import chromadb  # noqa: F401
            from mempalace.miner import get_collection  # noqa: F401
            from mempalace.searcher import search_memories  # noqa: F401
        except Exception:
            return False
        self._configure_chroma_cache()
        return True

    def _configure_chroma_cache(self) -> None:
        self.chroma_cache_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.chroma_cache_dir / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = str(temp_dir)
        os.environ["TEMP"] = str(temp_dir)
        os.environ["TMP"] = str(temp_dir)
        os.environ.setdefault("ORT_TENSORRT_CACHE_PATH", str(self.chroma_cache_dir / "ort_cache"))
        try:
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

            ONNXMiniLM_L6_V2.DOWNLOAD_PATH = self.chroma_cache_dir / "onnx_models" / ONNXMiniLM_L6_V2.MODEL_NAME
        except Exception:
            return

    def index_memory(self, memory: Memory) -> None:
        if not self._available:
            return None

        if os.getenv("CTO_OS_SYNC_MEMPALACE_INDEX") == "1":
            self._upsert_memory(memory)
            return None

        thread = threading.Thread(target=self._upsert_memory, args=(memory,), daemon=True)
        thread.start()
        return None

    def _upsert_memory(self, memory: Memory) -> None:
        from mempalace.miner import get_collection

        try:
            collection = get_collection(self.palace_path)
            room = "source_of_truth" if memory.pinned else "cto_os"
            drawer_id = self._drawer_id(memory)
            collection.upsert(
                documents=[f"{memory.title}\n\n{memory.content}"],
                ids=[drawer_id],
                metadatas=[
                    {
                        "wing": memory.project_id,
                        "room": room,
                        "source_file": f"cto_os://memories/{memory.id}",
                        "chunk_index": 0,
                        "added_by": "cto_os",
                        "filed_at": datetime.utcnow().isoformat(),
                        "project_id": memory.project_id,
                        "memory_id": memory.id,
                        "pinned": memory.pinned,
                        "tags": ",".join(memory.tags),
                    }
                ],
            )
        except Exception:
            self._available = False
            return None
        return None

    def search(self, project_id: str, query: str = "", cross_project: bool = False, limit: int = 8) -> list[Memory]:
        pinned = self.pinned_context(project_id)
        if not self._available or not query.strip():
            return super().search(project_id, query, cross_project=cross_project, limit=limit)

        def run_search() -> dict:
            from mempalace.searcher import search_memories

            return search_memories(
                query=query,
                palace_path=self.palace_path,
                wing=None if cross_project else project_id,
                n_results=limit,
            )

        timeout_seconds = float(os.getenv("CTO_OS_MEMPALACE_SEARCH_TIMEOUT", "8"))
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            result = executor.submit(run_search).result(timeout=timeout_seconds)
        except (Exception, TimeoutError):
            self._available = False
            return super().search(project_id, query, cross_project=cross_project, limit=limit)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if "error" in result:
            return super().search(project_id, query, cross_project=cross_project, limit=limit)

        memories = pinned[:]
        seen_ids = {memory.id for memory in memories}
        for hit in result.get("results", []):
            memory = self._hit_to_memory(hit, fallback_project_id=project_id)
            if memory.id not in seen_ids:
                memories.append(memory)
                seen_ids.add(memory.id)
        return memories[:limit]

    def _drawer_id(self, memory: Memory) -> str:
        digest = hashlib.md5(memory.id.encode(), usedforsecurity=False).hexdigest()[:16]
        return f"cto_os_{memory.project_id}_{digest}"

    def _hit_to_memory(self, hit: dict, fallback_project_id: str) -> Memory:
        text = hit.get("text", "")
        wing = hit.get("wing") or fallback_project_id
        room = hit.get("room", "mempalace")
        source = hit.get("source_file", "mempalace")
        digest = hashlib.md5(f"{wing}:{room}:{source}:{text}".encode(), usedforsecurity=False).hexdigest()[:12]
        return Memory(
            id=f"mp_{digest}",
            project_id=wing,
            title=f"{room} / {source}",
            content=text,
            tags=["mempalace", room],
            pinned=False,
            source=source,
        )

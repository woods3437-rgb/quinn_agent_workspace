"""AST parser test with a tiny Python/TS repo (Phase 6 verification)."""
from __future__ import annotations

from cto_os_api.repo_operator import RepoOperator


def test_ast_parser_indexes_python_and_typescript(store, memory_engine, project, repository):
    operator = RepoOperator(store, memory_engine)

    scan = operator.scan_repository(project.id, repository.id)

    symbols = store.list_code_symbols(project.id, repository.id)
    by_name = {(symbol.name, symbol.symbol_type) for symbol in symbols}

    # Python AST coverage
    assert ("Service", "class") in by_name
    assert ("health", "api_endpoint") in by_name, "FastAPI @app.get decorator must be detected"
    assert ("create_item", "api_endpoint") in by_name

    # The health endpoint should record its HTTP path in metadata
    health = next(
        sym for sym in symbols if sym.name == "health" and sym.symbol_type == "api_endpoint"
    )
    assert health.metadata.get("http_path") == "/health"

    # TS/JS coverage
    assert ("HomePage", "component") in by_name
    assert ("helper", "function") in by_name or ("helper", "export") in by_name
    assert ("GET", "route_handler") in by_name

    deps = {dep.dependency for dep in store.list_code_dependencies(project.id, repository.id)}
    assert "fastapi" in deps
    assert "react" in deps

    assert "Symbols:" in scan.summary
    assert "routes/api=" in scan.summary

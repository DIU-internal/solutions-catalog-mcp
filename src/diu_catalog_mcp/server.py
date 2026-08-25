from __future__ import annotations

import csv
from collections import Counter
from functools import lru_cache
from typing import Any

from fastmcp import FastMCP

from .config import Settings
from .models import CatalogRecord
from .vector_store import CatalogVectorStore, read_catalog

mcp = FastMCP(
    "DIU Solutions Catalog",
    instructions=(
        "Search and explore successful and transitioned Defense Innovation Unit "
        "commercial solutions. Use search_solutions for needs-based discovery, "
        "get_solution for complete details, and catalog_facets to discover filters."
    ),
)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def _store() -> CatalogVectorStore:
    settings = _settings()
    store = CatalogVectorStore(
        settings.qdrant_path,
        settings.collection_name,
        settings.embedding_model,
        model_cache_path=settings.model_cache_path,
    )
    if store.count() == 0:
        raise RuntimeError(
            "The DIU vector database is empty. Run `diu-catalog-ingest` before starting MCP."
        )
    return store


@lru_cache(maxsize=1)
def _records() -> tuple[CatalogRecord, ...]:
    return tuple(read_catalog(_settings().csv_path))


@mcp.tool
def search_solutions(
    query: str,
    limit: int = 10,
    portfolio: str | None = None,
    vendor: str | None = None,
    year_completed: str | None = None,
) -> list[dict[str, Any]]:
    """Semantically search DIU solutions by mission need, capability, problem, or keyword.

    Optional filters are exact values; call catalog_facets to see available values.
    Results include a cosine similarity score and full project details.
    """
    return _store().search(
        query,
        limit=limit,
        portfolio=portfolio,
        vendor=vendor,
        year_completed=year_completed,
    )


@mcp.tool
def get_solution(uuid: str) -> dict[str, str]:
    """Get one complete catalog solution by its DIU UUID."""
    for record in _records():
        if record.uuid == uuid:
            return record.public_dict()
    raise ValueError(f"No DIU catalog solution found for UUID: {uuid}")


@mcp.tool
def list_solutions(
    portfolio: str | None = None,
    vendor: str | None = None,
    year_completed: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Browse catalog projects with exact-value filters and pagination."""
    records = [
        record
        for record in _records()
        if (not portfolio or record.portfolio == portfolio)
        and (not vendor or record.vendor_name == vendor)
        and (not year_completed or record.year_completed == year_completed)
    ]
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, 100))
    page = records[safe_offset : safe_offset + safe_limit]
    return {
        "total": len(records),
        "offset": safe_offset,
        "limit": safe_limit,
        "solutions": [record.public_dict() for record in page],
    }


@mcp.tool
def catalog_facets() -> dict[str, list[dict[str, Any]]]:
    """List available focus areas, vendors, and completion years with record counts."""

    def counts(attribute: str) -> list[dict[str, Any]]:
        values = Counter(
            getattr(record, attribute) for record in _records() if getattr(record, attribute)
        )
        return [
            {"value": value, "count": count}
            for value, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        "portfolios": counts("portfolio"),
        "vendors": counts("vendor_name"),
        "years": counts("year_completed"),
    }


@mcp.tool
def catalog_status() -> dict[str, Any]:
    """Report the configured data paths and indexed record counts."""
    settings = _settings()
    with settings.csv_path.open(encoding="utf-8", newline="") as handle:
        csv_count = sum(1 for _ in csv.DictReader(handle))
    return {
        "csv_path": str(settings.csv_path.resolve()),
        "vector_db_path": str(settings.qdrant_path.resolve()),
        "collection": settings.collection_name,
        "embedding_model": settings.embedding_model,
        "model_cache_path": str(settings.model_cache_path.resolve()),
        "csv_records": csv_count,
        "indexed_records": _store().count(),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

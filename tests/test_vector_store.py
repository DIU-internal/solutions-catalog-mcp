from __future__ import annotations

from collections.abc import Iterable

from diu_catalog_mcp.models import CatalogRecord
from diu_catalog_mcp.vector_store import CatalogVectorStore


class KeywordEmbedder:
    def embed(self, documents: Iterable[str]):
        for document in documents:
            lowered = document.lower()
            yield [
                float("cyber" in lowered or "zero trust" in lowered),
                float("space" in lowered or "satellite" in lowered),
                0.01,
            ]


def record(uuid: str, project: str, portfolio: str, problem: str) -> CatalogRecord:
    return CatalogRecord(
        uuid=uuid,
        project_name=project,
        vendor_name="Vendor",
        portfolio=portfolio,
        year_completed="2025",
        dod_partners="",
        key_terms="",
        problem=problem,
        solution="Solution",
        key_terms_html="",
        problem_html="",
        solution_html="",
        source_url=f"https://example.test/{uuid}",
        scraped_at="2026-01-01T00:00:00+00:00",
    )


def test_rebuild_and_semantic_search(tmp_path) -> None:
    store = CatalogVectorStore(
        tmp_path / "qdrant", "test", "test-model", embedder=KeywordEmbedder()
    )
    store.rebuild(
        [
            record("cyber-1", "Identity Gateway", "Cyber", "Zero trust access"),
            record("space-1", "Orbit Watch", "Space", "Satellite awareness"),
        ]
    )

    results = store.search("cyber defense", limit=1)
    assert store.count() == 2
    assert results[0]["uuid"] == "cyber-1"


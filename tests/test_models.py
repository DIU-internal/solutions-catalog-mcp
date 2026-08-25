from diu_catalog_mcp.models import CatalogRecord


def test_search_document_uses_discovery_fields() -> None:
    record = CatalogRecord(
        uuid="abc",
        project_name="Edge Compute",
        vendor_name="Example Inc.",
        portfolio="AI/ML",
        year_completed="2025",
        dod_partners="USAF",
        key_terms="rugged edge inference",
        problem="Disconnected operations",
        solution="Portable compute nodes",
        key_terms_html="",
        problem_html="",
        solution_html="",
        source_url="https://example.test/abc",
        scraped_at="2026-01-01T00:00:00+00:00",
    )

    document = record.search_document()
    assert "Project: Edge Compute" in document
    assert "Problem: Disconnected operations" in document
    assert "Solution: Portable compute nodes" in document


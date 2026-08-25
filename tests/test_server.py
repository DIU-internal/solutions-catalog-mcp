from __future__ import annotations

from typing import Any

from fastmcp import Client

from diu_catalog_mcp import server
from diu_catalog_mcp.models import CatalogRecord


def sample_record() -> CatalogRecord:
    return CatalogRecord(
        uuid="solution-1",
        project_name="Autonomous Harbor Watch",
        vendor_name="Example Robotics",
        portfolio="Autonomous Warfare Portfolio",
        year_completed="2025",
        dod_partners="US Navy",
        key_terms="maritime autonomy",
        problem="Persistent harbor monitoring",
        solution="Autonomous surface vessel",
        key_terms_html="",
        problem_html="",
        solution_html="",
        source_url="https://example.test/solution-1",
        scraped_at="2026-01-01T00:00:00+00:00",
    )


class FakeStore:
    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        assert query == "harbor security"
        return [{"score": 0.9, **sample_record().public_dict()}]


async def test_mcp_discovery_tools(monkeypatch) -> None:
    monkeypatch.setattr(server, "_store", lambda: FakeStore())
    monkeypatch.setattr(server, "_records", lambda: (sample_record(),))

    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "search_solutions",
            "get_solution",
            "list_solutions",
            "catalog_facets",
            "catalog_status",
        }

        search = await client.call_tool(
            "search_solutions", {"query": "harbor security", "limit": 1}
        )
        assert search.structured_content["result"][0]["uuid"] == "solution-1"

        detail = await client.call_tool("get_solution", {"uuid": "solution-1"})
        assert detail.structured_content["project_name"] == "Autonomous Harbor Watch"

        listing = await client.call_tool(
            "list_solutions", {"portfolio": "Autonomous Warfare Portfolio"}
        )
        assert listing.structured_content["total"] == 1

        facets = await client.call_tool("catalog_facets", {})
        assert facets.structured_content["portfolios"] == [
            {"value": "Autonomous Warfare Portfolio", "count": 1}
        ]


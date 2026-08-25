from __future__ import annotations

import httpx

from diu_catalog_mcp.scraper import (
    DETAIL_API_URL,
    SUMMARY_API_URL,
    _year_number,
    html_to_text,
    scrape_catalog,
)


def test_html_to_text_normalizes_markup() -> None:
    assert html_to_text("<p>Hello <strong>DIU</strong></p><p>Catalog</p>") == "Hello DIU Catalog"


def test_year_number_handles_full_dates() -> None:
    assert _year_number("11 Oct 2022") == 2022
    assert _year_number("") == 0


async def test_scrape_catalog_merges_summary_and_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(SUMMARY_API_URL):
            return httpx.Response(
                200,
                json={
                    "statusCode": "200",
                    "body": {
                        "result": {
                            "totalRecords": 1,
                            "catalog": [
                                {
                                    "uuid": "project-1",
                                    "projectName": "Test Project",
                                    "vendorName": "Test Vendor",
                                    "portfolio": "Cyber Portfolio",
                                    "yearReferenced": "2025",
                                    "key_terms": "<p>zero trust</p>",
                                }
                            ],
                        }
                    },
                },
            )
        assert str(request.url).startswith(DETAIL_API_URL)
        return httpx.Response(
            200,
            json={
                "statusCode": "200",
                "body": {
                    "result": [
                        {
                            "uuid": "project-1",
                            "problemArea": "<p>Legacy access controls</p>",
                            "solution": "<p>Identity-aware proxy</p>",
                            "dodPartners": "USAF",
                        }
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await scrape_catalog(client=client)

    assert len(records) == 1
    assert records[0].key_terms == "zero trust"
    assert records[0].problem == "Legacy access controls"
    assert records[0].solution == "Identity-aware proxy"
    assert records[0].source_url.endswith("/project-1")

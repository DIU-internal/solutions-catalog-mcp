from __future__ import annotations

import argparse
import asyncio
import csv
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .models import CatalogRecord
from .tls import system_ssl_context

CATALOG_PAGE_URL = "https://www.diu.mil/solutions/portfolio/catalog"
SUMMARY_API_URL = "https://5gyku0bs5b.execute-api.us-gov-west-1.amazonaws.com/default"
DETAIL_API_URL = "https://2vy666ugmj.execute-api.us-gov-west-1.amazonaws.com/default/"
DEFAULT_OUTPUT = Path("data/diu_solutions_catalog.csv")
USER_AGENT = "diu-solutions-catalog-mcp/0.1 (+catalog research)"


class ScrapeError(RuntimeError):
    """Raised when the catalog cannot be scraped completely."""


def html_to_text(value: Any) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(str(value), "html.parser")
    return " ".join(soup.stripped_strings)


def _body(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("body", payload)
    if isinstance(body, str):
        import json

        body = json.loads(body)
    if not isinstance(body, dict):
        raise ScrapeError("DIU API returned an unexpected response body")
    return body


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
    retries: int = 4,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            status_code = str(payload.get("statusCode", "200"))
            if not status_code.startswith("2"):
                raise ScrapeError(f"DIU API reported status {status_code}")
            return payload
        except (httpx.HTTPError, ValueError, ScrapeError) as exc:
            last_error = exc
            if attempt == retries:
                break
            await asyncio.sleep((0.4 * 2**attempt) + random.random() * 0.2)
    raise ScrapeError(f"Request failed after {retries + 1} attempts: {url}") from last_error


async def fetch_summaries(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    payload = await _get_json(
        client,
        SUMMARY_API_URL,
        params={"limit": 1000, "offset": 0, "q": ""},
    )
    result = _body(payload).get("result", {})
    records = result.get("catalog", [])
    expected = int(result.get("totalRecords", len(records)))
    if not isinstance(records, list) or len(records) != expected:
        raise ScrapeError(f"Expected {expected} catalog records but received {len(records)}")
    return records


async def fetch_detail(
    client: httpx.AsyncClient,
    summary: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    uuid = str(summary.get("uuid") or "")
    if not uuid:
        raise ScrapeError("Catalog summary is missing a UUID")
    async with semaphore:
        payload = await _get_json(client, DETAIL_API_URL, params={"uuid": uuid})
    result = _body(payload).get("result", [])
    if not isinstance(result, list) or len(result) != 1:
        raise ScrapeError(f"Expected one detail record for {uuid}, received {len(result)}")
    return {**summary, **result[0]}


def normalize_record(raw: dict[str, Any], scraped_at: str) -> CatalogRecord:
    uuid = str(raw.get("uuid") or "")
    key_terms_html = str(raw.get("key_terms") or "")
    problem_html = str(raw.get("problemArea") or "")
    solution_html = str(raw.get("solution") or "")
    return CatalogRecord(
        uuid=uuid,
        project_name=html_to_text(raw.get("projectName")),
        vendor_name=html_to_text(raw.get("vendorName")),
        portfolio=html_to_text(raw.get("portfolio")),
        year_completed=html_to_text(raw.get("yearReferenced")),
        dod_partners=html_to_text(raw.get("dodPartners")),
        key_terms=html_to_text(key_terms_html),
        problem=html_to_text(problem_html),
        solution=html_to_text(solution_html),
        key_terms_html=key_terms_html,
        problem_html=problem_html,
        solution_html=solution_html,
        source_url=f"{CATALOG_PAGE_URL}/{uuid}",
        scraped_at=scraped_at,
    )


async def scrape_catalog(
    *,
    concurrency: int = 12,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> list[CatalogRecord]:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            verify=system_ssl_context(),
        )
    try:
        summaries = await fetch_summaries(client)
        semaphore = asyncio.Semaphore(max(1, concurrency))
        details = await asyncio.gather(
            *(fetch_detail(client, summary, semaphore) for summary in summaries)
        )
    finally:
        if owns_client:
            await client.aclose()

    scraped_at = datetime.now(timezone.utc).isoformat()
    records = [normalize_record(detail, scraped_at) for detail in details]
    records.sort(key=lambda item: (-_year_number(item.year_completed), item.project_name.lower()))
    return records


def _year_number(value: str) -> int:
    match = re.search(r"\b(?:19|20)\d{2}\b", value)
    return int(match.group()) if match else 0


def write_csv(records: list[CatalogRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CatalogRecord.csv_fields())
        writer.writeheader()
        writer.writerows(record.to_dict() for record in records)
    temporary_path.replace(output_path)


async def run(output_path: Path, concurrency: int, timeout: float) -> int:
    records = await scrape_catalog(concurrency=concurrency, timeout=timeout)
    write_csv(records, output_path)
    print(f"Wrote {len(records)} records to {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape the complete DIU solutions catalog")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    return asyncio.run(run(args.output, args.concurrency, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())

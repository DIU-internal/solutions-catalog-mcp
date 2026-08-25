# DIU Solutions Catalog MCP

A Python [FastMCP](https://gofastmcp.com/) server for searching and discovering projects
in the [DIU Commercial Solutions Catalog](https://www.diu.mil/solutions/portfolio/catalog).

The project provides a reproducible pipeline that:

1. Fetches every catalog entry from DIU's public catalog and detail APIs.
2. Writes the complete data set to one CSV, including plain text and original HTML fields.
3. Embeds the records with FastEmbed and persists them in an embedded Qdrant database.
4. Exposes semantic search, exact lookup, browsing, facets, and status through FastMCP.

## Quick start

Python 3.10 or newer and [uv](https://docs.astral.sh/uv/) are recommended.

```bash
uv sync --extra dev
uv run diu-catalog-scrape
uv run diu-catalog-ingest
uv run diu-catalog-mcp
```

The default MCP transport is stdio. Add it to an MCP client with:

```json
{
  "mcpServers": {
    "diu-solutions": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/solutions-catalog-mcp", "run", "diu-catalog-mcp"]
    }
  }
}
```

## Data pipeline

Scrape the full catalog:

```bash
uv run diu-catalog-scrape --output data/diu_solutions_catalog.csv
```

The command validates DIU's reported total, fetches each detail record concurrently with retries,
and atomically replaces the CSV only after the scrape succeeds. The CSV columns are:

- `uuid`, `project_name`, `vendor_name`, `portfolio`, `year_completed`
- `dod_partners`, `key_terms`, `problem`, `solution`
- `key_terms_html`, `problem_html`, `solution_html`
- `source_url`, `scraped_at`

Build or rebuild the vector database:

```bash
uv run diu-catalog-ingest \
  --csv data/diu_solutions_catalog.csv \
  --db data/qdrant
```

The default embedding model is `BAAI/bge-small-en-v1.5` (384 dimensions). It is downloaded on
the first ingestion. Rebuilding replaces the collection only after the CSV and first embedding
have been validated.

## MCP tools

- `search_solutions`: semantic search by mission need, capability, problem, or keyword; supports
  exact portfolio, vendor, and year filters.
- `get_solution`: retrieve a full project by DIU UUID.
- `list_solutions`: browse and filter the catalog with pagination.
- `catalog_facets`: list focus areas, vendors, and years with counts.
- `catalog_status`: report data paths and CSV/vector record counts.

Example discovery requests:

- "Find solutions for resilient communications in disconnected environments."
- "Show autonomous maritime systems completed in 2025."
- "Which catalog entries address zero-trust access or identity management?"

## Configuration

Environment variables override the defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DIU_CATALOG_CSV` | `data/diu_solutions_catalog.csv` | Scraped catalog CSV |
| `DIU_QDRANT_PATH` | `data/qdrant` | Embedded Qdrant storage directory |
| `DIU_COLLECTION` | `diu_solutions` | Qdrant collection name |
| `DIU_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed model |
| `DIU_MODEL_CACHE` | `data/models` | Persistent embedding model cache |

## Development

```bash
uv run pytest
uv run ruff check .
```

The scraper tests use mocked HTTP responses. The vector test uses a deterministic in-memory test
embedder, so the test suite does not download a model.

## Data provenance

All catalog content comes from DIU's public website/API and remains attributable through each
row's `source_url`. Re-run the scraper and ingestion commands to refresh the local snapshot.

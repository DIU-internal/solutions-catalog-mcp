from __future__ import annotations

import argparse
import csv
import hashlib
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from .config import Settings
from .models import CatalogRecord
from .tls import configure_system_trust


class Embedder(Protocol):
    def embed(self, documents: Iterable[str]) -> Iterable[Sequence[float]]: ...


def read_catalog(path: Path) -> list[CatalogRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Catalog CSV does not exist: {path}. Run diu-catalog-scrape.")
    with path.open(encoding="utf-8", newline="") as handle:
        records = [CatalogRecord.from_row(row) for row in csv.DictReader(handle)]
    if not records:
        raise ValueError(f"Catalog CSV contains no records: {path}")
    return records


def stable_point_id(uuid: str) -> int:
    return int.from_bytes(hashlib.sha256(uuid.encode()).digest()[:8], "big") & ((1 << 63) - 1)


class CatalogVectorStore:
    def __init__(
        self,
        path: Path,
        collection_name: str,
        embedding_model: str,
        *,
        model_cache_path: Path | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        configure_system_trust()
        path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(path))
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        if embedder is not None:
            self.embedder = embedder
        else:
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            from fastembed import TextEmbedding

            cache_path = model_cache_path or Path("data/models")
            cache_path.mkdir(parents=True, exist_ok=True)
            self.embedder = TextEmbedding(
                model_name=embedding_model,
                cache_dir=str(cache_path),
            )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [list(vector) for vector in self.embedder.embed(texts)]

    def rebuild(self, records: list[CatalogRecord], batch_size: int = 32) -> int:
        first_vector = self._embed([records[0].search_document()])[0]
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=len(first_vector), distance=models.Distance.COSINE
            ),
        )

        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            if start == 0:
                vectors = [first_vector]
                vectors.extend(self._embed([record.search_document() for record in batch[1:]]))
            else:
                vectors = self._embed([record.search_document() for record in batch])
            points = [
                models.PointStruct(
                    id=stable_point_id(record.uuid),
                    vector=vector,
                    payload=record.public_dict(),
                )
                for record, vector in zip(batch, vectors, strict=True)
            ]
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(records)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        portfolio: str | None = None,
        vendor: str | None = None,
        year_completed: str | None = None,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query must not be empty")
        conditions: list[models.FieldCondition] = []
        for key, value in (
            ("portfolio", portfolio),
            ("vendor_name", vendor),
            ("year_completed", year_completed),
        ):
            if value:
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )
        query_filter = models.Filter(must=conditions) if conditions else None
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=self._embed([query])[0],
            query_filter=query_filter,
            limit=max(1, min(limit, 50)),
            with_payload=True,
        )
        return [
            {"score": round(float(point.score), 6), **dict(point.payload or {})}
            for point in response.points
        ]

    def count(self) -> int:
        if not self.client.collection_exists(self.collection_name):
            return 0
        return int(self.client.count(self.collection_name, exact=True).count)


def main() -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Build the local DIU catalog vector database")
    parser.add_argument("--csv", type=Path, default=settings.csv_path)
    parser.add_argument("--db", type=Path, default=settings.qdrant_path)
    parser.add_argument("--collection", default=settings.collection_name)
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--model-cache", type=Path, default=settings.model_cache_path)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    records = read_catalog(args.csv)
    store = CatalogVectorStore(
        args.db,
        args.collection,
        args.model,
        model_cache_path=args.model_cache,
    )
    count = store.rebuild(records, batch_size=args.batch_size)
    print(f"Indexed {count} records in {args.db} (collection: {args.collection})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

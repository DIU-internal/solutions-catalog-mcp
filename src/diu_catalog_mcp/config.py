from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    csv_path: Path
    qdrant_path: Path
    collection_name: str
    embedding_model: str
    model_cache_path: Path

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            csv_path=Path(os.getenv("DIU_CATALOG_CSV", "data/diu_solutions_catalog.csv")),
            qdrant_path=Path(os.getenv("DIU_QDRANT_PATH", "data/qdrant")),
            collection_name=os.getenv("DIU_COLLECTION", "diu_solutions"),
            embedding_model=os.getenv(
                "DIU_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
            ),
            model_cache_path=Path(os.getenv("DIU_MODEL_CACHE", "data/models")),
        )

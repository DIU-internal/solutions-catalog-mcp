from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(slots=True)
class CatalogRecord:
    uuid: str
    project_name: str
    vendor_name: str
    portfolio: str
    year_completed: str
    dod_partners: str
    key_terms: str
    problem: str
    solution: str
    key_terms_html: str
    problem_html: str
    solution_html: str
    source_url: str
    scraped_at: str

    @classmethod
    def csv_fields(cls) -> list[str]:
        return [field.name for field in fields(cls)]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> CatalogRecord:
        values = {name: str(row.get(name) or "") for name in cls.csv_fields()}
        return cls(**values)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def search_document(self) -> str:
        sections = [
            f"Project: {self.project_name}",
            f"Company: {self.vendor_name}",
            f"DIU focus area: {self.portfolio}",
            f"Year completed: {self.year_completed}",
            f"DoD partners: {self.dod_partners}",
            f"Key terms: {self.key_terms}",
            f"Problem: {self.problem}",
            f"Solution: {self.solution}",
        ]
        return "\n".join(section for section in sections if not section.endswith(": "))

    def public_dict(self) -> dict[str, str]:
        """Return useful fields without duplicative raw HTML."""
        return {
            "uuid": self.uuid,
            "project_name": self.project_name,
            "vendor_name": self.vendor_name,
            "portfolio": self.portfolio,
            "year_completed": self.year_completed,
            "dod_partners": self.dod_partners,
            "key_terms": self.key_terms,
            "problem": self.problem,
            "solution": self.solution,
            "source_url": self.source_url,
        }

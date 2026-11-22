"""Shared record types used by collection and validation modules."""
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class SourceRecord:
    entity_type: str
    name: str
    source_url: str
    published_at: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def has_traceable_source(record: dict[str, Any]) -> bool:
    url = str(record.get("source_url") or record.get("url") or "").strip()
    return url.startswith(("https://", "http://"))

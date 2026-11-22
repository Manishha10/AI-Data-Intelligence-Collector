"""Conservative entity matching utilities.

Automatic matches are suggestions only. Keep original names and source URLs;
review ambiguous matches before merging records.
"""
import re
from difflib import SequenceMatcher

def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())

def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio()

def suggest_match(name: str, known_entities: list[dict], threshold: float = 0.92) -> dict | None:
    ranked = sorted(((similarity(name, str(row.get("name", ""))), row) for row in known_entities),
                    key=lambda pair: pair[0], reverse=True)
    if ranked and ranked[0][0] >= threshold:
        return {"score": ranked[0][0], "candidate": ranked[0][1], "status": "needs_review"}
    return None

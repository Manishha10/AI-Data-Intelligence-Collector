"""Dataset quality checks for exported records."""
from datetime import datetime, timezone, timedelta
from .models import has_traceable_source

def validate_rows(rows: list[dict], *, freshness_hours: int | None = None,
                  timestamp_key: str = "published_at") -> dict:
    now = datetime.now(timezone.utc)
    valid, issues = [], []
    for index, row in enumerate(rows):
        if not has_traceable_source(row):
            issues.append({"row": index, "issue": "missing_traceable_source_url"})
            continue
        if freshness_hours is not None:
            raw = row.get(timestamp_key)
            try:
                stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                if stamp < now - timedelta(hours=freshness_hours) or stamp > now + timedelta(minutes=5):
                    issues.append({"row": index, "issue": "outside_freshness_window"})
                    continue
            except Exception:
                issues.append({"row": index, "issue": "missing_or_invalid_timestamp"})
                continue
        valid.append(row)
    return {"valid_rows": valid, "issues": issues, "valid_count": len(valid), "issue_count": len(issues)}

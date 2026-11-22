"""LLM extraction adapter with provider fallback.

No provider is called unless its SDK/key is configured. The adapter retries a
fallback provider for transient/provider-limit failures. It does not fabricate
records: callers must validate extracted fields against the source text/URL.
"""
from typing import Any, Callable

class ExtractionError(RuntimeError):
    pass

async def extract_with_fallback(primary: Callable[..., Any] | None,
                                fallback: Callable[..., Any] | None,
                                *, text: str, source_url: str) -> Any:
    if not source_url.startswith(("https://", "http://")):
        raise ValueError("A traceable HTTP(S) source URL is required")
    errors = []
    for provider in (primary, fallback):
        if provider is None:
            continue
        try:
            # Provider callable is expected to be async and return structured data.
            return await provider(text=text, source_url=source_url)
        except Exception as exc:
            message = str(exc).lower()
            retryable = any(code in message for code in ("413", "429", "rate limit", "timeout", "temporarily"))
            errors.append(f"{type(exc).__name__}: {exc}")
            if not retryable:
                continue
    raise ExtractionError("No configured provider completed extraction. " + " | ".join(errors))

def validate_extraction(item: dict[str, Any], source_url: str) -> dict[str, Any]:
    if not source_url.startswith(("https://", "http://")):
        raise ValueError("Invalid source URL")
    if not isinstance(item, dict):
        raise TypeError("Extraction must be a JSON-like object")
    item["source_url"] = source_url
    return item

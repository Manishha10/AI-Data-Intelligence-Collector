"""Small async HTTP crawler utility with concurrency and timeout controls.

This is a reusable fetch layer, not a guarantee of access to every website.
Respect each site's terms, robots policy, rate limits and access controls.
It intentionally does not bypass CAPTCHAs, logins, paywalls or anti-bot protections.
"""
import asyncio
from typing import Iterable
import aiohttp
from .config import settings

async def fetch_text(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=settings.request_timeout)) as response:
        response.raise_for_status()
        return url, await response.text()

async def fetch_many(urls: Iterable[str]) -> list[dict[str, str]]:
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    async with aiohttp.ClientSession(headers={"User-Agent": "AIDataCollector/1.0 (research; contact: repository-owner)"}) as session:
        async def bounded(url: str):
            async with semaphore:
                try:
                    source_url, body = await fetch_text(session, url)
                    return {"source_url": source_url, "body": body, "error": ""}
                except Exception as exc:
                    return {"source_url": url, "body": "", "error": str(exc)}
        return await asyncio.gather(*(bounded(u) for u in urls))

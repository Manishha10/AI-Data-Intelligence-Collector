# Additional project modules

These files add reusable modules to the existing collector repository.

## Contents
- `src/crawler.py`: asynchronous HTTP fetch utility with concurrency and timeout controls.
- `src/llm_extractor.py`: provider-agnostic extraction interface and fallback handling.
- `src/entity_resolver.py`: conservative fuzzy-match suggestions; ambiguous matches require review.
- `src/validation.py`: traceable URL and timestamp/freshness checks.
- `src/config.py`, `src/models.py`: shared settings and record types.
- `docs/architecture.pdf`: architecture overview and known limitations.

## Important integration note
These modules are reusable building blocks. They are not automatically wired into the existing `collect_data.py` script. Provider SDK calls, provider-specific adapters, source-specific parsers, a verified 50-company canonical entity list, and Google Sheets publishing still need configuration/integration before claiming those requirements are complete.

## Install
`pip install aiohttp`

The LLM adapter accepts async provider callables; do not put API keys in source code. Set secrets as environment variables. Never claim a record is AI-related or fresh without validating its source and timestamp.

# job-aggregator

job-aggregator is a backend service for aggregating developer vacancies.

## Stack

- Python 3.14
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- aiohttp / asyncio
- APScheduler
- pytest
- uv

## Local setup

```bash
uv sync
cp .env.example .env
uv run uvicorn job_aggregator.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Tests

```bash
uv run pytest
```

## Project structure

```text
src/job_aggregator/
├── api/        # FastAPI routers and endpoints
├── core/       # configuration and logging
├── db/         # SQLAlchemy engine, sessions, base metadata
└── main.py     # application factory
```
